"""This module contains helper functions for accessing data."""
from typing import Optional, Iterable, Tuple, Mapping, Union, Sequence

import numpy as np
import pandas as pd
from pandas.api.types import is_categorical_dtype
from scipy.sparse import spmatrix

from anndata import AnnData
from ._utils import sanitize_anndata

_VarNames = Union[str, Sequence[str]]

# --------------------------------------------------------------------------------
# Plotting data helpers
# --------------------------------------------------------------------------------


# TODO: implement diffxpy method, make singledispatch
def rank_genes_groups_df(
    adata: AnnData,
    group: str,  # Can this be something other than a str?
    *,
    key: str = "rank_genes_groups",
    pval_cutoff: Optional[float] = None,
    log2fc_min: Optional[float] = None,
    log2fc_max: Optional[float] = None,
    gene_symbols: Optional[str] = None,
) -> pd.DataFrame:
    """\
    :func:`scanpy.tl.rank_genes_groups` results in the form of a
    :class:`~pandas.DataFrame`.

    Params
    ------
    adata
        Object to get results from.
    group
        Which group (as in :func:`scanpy.tl.rank_genes_groups`'s `groupby`
        argument) to return results from.
    key
        Key differential expression groups were stored under.
    pval_cutoff
        Minimum adjusted pval to return.
    log2fc_min
        Minumum logfc to return.
    log2fc_max
        Maximum logfc to return.
    gene_symbols
        Column name in `.var` DataFrame that stores gene symbols. Specifying
        this will add that column to the returned dataframe.

    Example
    -------
    >>> import scanpy as sc
    >>> pbmc = sc.datasets.pbmc68k_reduced()
    >>> sc.tl.rank_genes_groups(pbmc, groupby="louvain", use_raw=True, n_genes=pbmc.shape[1])
    >>> dedf = sc.get.rank_genes_groups_df(pbmc, group="0")
    """
    d = pd.DataFrame()
    for k in ['scores', 'names', 'logfoldchanges', 'pvals', 'pvals_adj']:
        d[k] = adata.uns[key][k][group]
    if pval_cutoff is not None:
        d = d[d["pvals_adj"] < pval_cutoff]
    if log2fc_min is not None:
        d = d[d["logfoldchanges"] > log2fc_min]
    if log2fc_max is not None:
        d = d[d["logfoldchanges"] < log2fc_max]
    if gene_symbols is not None:
        d = d.join(adata.var[gene_symbols], on="names")
    return d


def obs_df(
    adata: AnnData,
    keys: Iterable[str] = (),
    obsm_keys: Iterable[Tuple[str, int]] = (),
    *,
    layer: str = None,
    gene_symbols: str = None,
    use_raw: bool = False,
) -> pd.DataFrame:
    """\
    Return values for observations in adata.

    Params
    ------
    adata
        AnnData object to get values from.
    keys
        Keys from either `.var_names`, `.var[gene_symbols]`, or `.obs.columns`.
    obsm_keys
        Tuple of `(key from obsm, column index of obsm[key])`.
    layer
        Layer of `adata` to use as expression values.
    gene_symbols
        Column of `adata.var` to search for `keys` in.
    use_raw
        Whether to get expression values from `adata.raw`.

    Returns
    -------
    A dataframe with `adata.obs_names` as index, and values specified by `keys`
    and `obsm_keys`.

    Examples
    --------
    Getting value for plotting:

    >>> pbmc = sc.datasets.pbmc68k_reduced()
    >>> plotdf = sc.get.obs_df(
            pbmc,
            keys=["CD8B", "n_genes"],
            obsm_keys=[("X_umap", 0), ("X_umap", 1)]
        )
    >>> plotdf.plot.scatter("X_umap0", "X_umap1", c="CD8B")

    Calculating mean expression for marker genes by cluster:

    >>> pbmc = sc.datasets.pbmc68k_reduced()
    >>> marker_genes = ['CD79A', 'MS4A1', 'CD8A', 'CD8B', 'LYZ']
    >>> genedf = sc.get.obs_df(
            pbmc,
            keys=["louvain", *marker_genes]
        )
    >>> grouped = genedf.groupby("louvain")
    >>> mean, var = grouped.mean(), grouped.var()
    """
    if use_raw:
        assert (
            layer is None
        ), "Cannot specify use_raw=True and a layer at the same time."
        if gene_symbols is not None:
            gene_names = pd.Series(
                adata.raw.var_names, index=adata.raw.var[gene_symbols]
            )
        else:
            gene_names = pd.Series(adata.raw.var_names, index=adata.raw.var_names)
    else:
        if gene_symbols is not None:
            gene_names = pd.Series(adata.var_names, index=adata.var[gene_symbols])
        else:
            gene_names = pd.Series(adata.var_names, index=adata.var_names)
    lookup_keys = []
    not_found = []
    for key in keys:
        if key in adata.obs.columns:
            lookup_keys.append(key)
        elif key in gene_names.index:
            lookup_keys.append(gene_names[key])
        else:
            not_found.append(key)
    if len(not_found) > 0:
        if use_raw:
            if gene_symbols is None:
                gene_error = "`adata.raw.var_names`"
            else:
                gene_error = "gene_symbols column `adata.raw.var[{}].values`".format(
                    gene_symbols
                )
        else:
            if gene_symbols is None:
                gene_error = "`adata.var_names`"
            else:
                gene_error = "gene_symbols column `adata.var[{}].values`".format(
                    gene_symbols
                )
        raise KeyError(
            f"Could not find keys '{not_found}' in columns of `adata.obs` or in"
            f" {gene_error}."
        )

    # Make df
    df = pd.DataFrame(index=adata.obs_names)
    for k, l in zip(keys, lookup_keys):
        if not use_raw or k in adata.obs.columns:
            df[k] = adata.obs_vector(l, layer=layer)
        else:
            df[k] = adata.raw.obs_vector(l)
    for k, idx in obsm_keys:
        added_k = f"{k}-{idx}"
        val = adata.obsm[k]
        if isinstance(val, np.ndarray):
            df[added_k] = np.ravel(val[:, idx])
        elif isinstance(val, spmatrix):
            df[added_k] = np.ravel(val[:, idx].toarray())
        elif isinstance(val, pd.DataFrame):
            df[added_k] = val.loc[:, idx]
    return df


def var_df(
    adata: AnnData,
    keys: Iterable[str] = (),
    varm_keys: Iterable[Tuple[str, int]] = (),
    *,
    layer: str = None,
) -> pd.DataFrame:
    """\
    Return values for observations in adata.

    Params
    ------
    adata
        AnnData object to get values from.
    keys
        Keys from either `.obs_names`, or `.var.columns`.
    varm_keys
        Tuple of `(key from varm, column index of varm[key])`.
    layer
        Layer of `adata` to use as expression values.

    Returns
    -------
    A dataframe with `adata.var_names` as index, and values specified by `keys`
    and `varm_keys`.
    """
    # Argument handling
    lookup_keys = []
    not_found = []
    for key in keys:
        if key in adata.var.columns:
            lookup_keys.append(key)
        elif key in adata.obs_names:
            lookup_keys.append(key)
        else:
            not_found.append(key)
    if len(not_found) > 0:
        raise KeyError(
            f"Could not find keys '{not_found}' in columns of `adata.var` or"
            " in `adata.obs_names`."
        )

    # Make df
    df = pd.DataFrame(index=adata.var_names)
    for k, l in zip(keys, lookup_keys):
        df[k] = adata.var_vector(l, layer=layer)
    for k, idx in varm_keys:
        added_k = f"{k}-{idx}"
        val = adata.varm[k]
        if isinstance(val, np.ndarray):
            df[added_k] = np.ravel(val[:, idx])
        elif isinstance(val, spmatrix):
            df[added_k] = np.ravel(val[:, idx].toarray())
        elif isinstance(val, pd.DataFrame):
            df[added_k] = val.loc[:, idx]
    return df


def _get_obs_rep(adata, *, use_raw=False, layer=None, obsm=None, obsp=None):
    """
    Choose array aligned with obs annotation.
    """
    is_layer = layer is not None
    is_raw = use_raw is not False
    is_obsm = obsm is not None
    is_obsp = obsp is not None
    choices_made = sum((is_layer, is_raw, is_obsm, is_obsp))
    assert choices_made <= 1
    if choices_made == 0:
        return adata.X
    elif is_layer:
        return adata.layers[layer]
    elif use_raw:
        return adata.raw.X
    elif is_obsm:
        return adata.obsm[obsm]
    elif is_obsp:
        return adata.obsp[obsp]
    else:
        assert False, (
            "That was unexpected. Please report this bug at:\n\n\t"
            " https://github.com/theislab/scanpy/issues"
        )


def _set_obs_rep(adata, val, *, use_raw=False, layer=None, obsm=None, obsp=None):
    """
    Set value for observation rep.
    """
    is_layer = layer is not None
    is_raw = use_raw is not False
    is_obsm = obsm is not None
    is_obsp = obsp is not None
    choices_made = sum((is_layer, is_raw, is_obsm, is_obsp))
    assert choices_made <= 1
    if choices_made == 0:
        adata.X = val
    elif is_layer:
        adata.layers[layer] = val
    elif use_raw:
        adata.raw.X = val
    elif is_obsm:
        adata.obsm[obsm] = val
    elif is_obsp:
        adata.obsp[obsp] = val
    else:
        assert False, (
            "That was unexpected. Please report this bug at:\n\n\t"
            " https://github.com/theislab/scanpy/issues"
        )


def _prepare_dataframe(
    adata: AnnData,
    var_names: Optional[Union[_VarNames, Mapping[str, _VarNames]]] = None,
    groupby: Optional[Union[str, Sequence[str]]] = None,
    use_raw: Optional[bool] = None,
    log: bool = False,
    num_categories: int = 7,
    layer: Optional[str] = None,
    gene_symbols: Optional[str] = None,
    concat_indices: bool = True,
):
    """
    Given the anndata object, prepares a data frame in which the row index are the categories
    defined by group by and the columns correspond to var_names.

    Parameters
    ----------
    adata
        Annotated data matrix.
    var_names
        `var_names` should be a valid subset of `adata.var_names`. All genes are used if no
        given.
    groupby
        The key of the observation grouping to consider. It is expected that
        groupby is a categorical. If groupby is not a categorical observation,
        it would be subdivided into `num_categories`.
    use_raw
        Use `raw` attribute of `adata` if present.
    log
        Use the log of the values
    num_categories
        Only used if groupby observation is not categorical. This value
        determines the number of groups into which the groupby observation
        should be subdivided.
    gene_symbols
        Key for field in .var that stores gene symbols.
    concat_indices
        Concatenates categorical indices into a single categorical index, if 
        groupby is a sequence. True by default.

    Returns
    -------
    Tuple of `pandas.DataFrame` and list of categories.
    """
    from scipy.sparse import issparse

    sanitize_anndata(adata)
    if use_raw is None and adata.raw is not None:
        use_raw = True
    if isinstance(var_names, str):
        var_names = [var_names]
    if var_names is None:
        if use_raw:
            var_names = adata.raw.var_names.values
        else:
            var_names = adata.var_names.values

    if groupby is not None:
        if isinstance(groupby, str):
            # if not a list, turn into a list
            groupby = [groupby]
        for group in groupby:
            if group not in adata.obs_keys():
                raise ValueError(
                    'groupby has to be a valid observation. '
                    f'Given {group}, is not in observations: {adata.obs_keys()}'
                )

    if gene_symbols is not None and gene_symbols in adata.var.columns:
        # translate gene_symbols to var_names
        # slow method but gives a meaningful error if no gene symbol is found:
        translated_var_names = []
        # if we're using raw to plot, we should also do gene symbol translations
        # using raw
        if use_raw:
            adata_or_raw = adata.raw
        else:
            adata_or_raw = adata
        for symbol in var_names:
            if symbol not in adata_or_raw.var[gene_symbols].values:
                logg.error(
                    f"Gene symbol {symbol!r} not found in given "
                    f"gene_symbols column: {gene_symbols!r}"
                )
                return
            translated_var_names.append(
                adata_or_raw.var[adata_or_raw.var[gene_symbols] == symbol].index[0]
            )
        symbols = var_names
        var_names = translated_var_names
    if layer is not None:
        if layer not in adata.layers.keys():
            raise KeyError(
                f'Selected layer: {layer} is not in the layers list. '
                f'The list of valid layers is: {adata.layers.keys()}'
            )
        matrix = adata[:, var_names].layers[layer]
    elif use_raw:
        matrix = adata.raw[:, var_names].X
    else:
        matrix = adata[:, var_names].X

    if issparse(matrix):
        matrix = matrix.toarray()
    if log:
        matrix = np.log1p(matrix)

    obs_tidy = pd.DataFrame(matrix, columns=var_names)
    if groupby is None:
        groupby = ''
        obs_tidy_idx = pd.Series(np.repeat('', len(obs_tidy))).astype('category')
    else:
        if len(groupby) == 1 and not is_categorical_dtype(adata.obs[groupby[0]]):
            # if the groupby column is not categorical, turn it into one
            # by subdividing into  `num_categories` categories
            obs_tidy_idx = pd.cut(adata.obs[groupby[0]], num_categories)
            idx_categories = obs_tidy_idx.cat.categories
        else:
            assert all(is_categorical_dtype(adata.obs[group]) for group in groupby)
            if concat_indices:
                obs_tidy_idx = adata.obs[groupby[0]]
                if len(groupby) > 1:
                    for group in groupby[1:]:
                        # create new category by merging the given groupby categories
                        obs_tidy_idx = (
                            obs_tidy_idx.astype(str) + "_" + adata.obs[group].astype(str)
                        ).astype('category')
                obs_tidy_idx.name = "_".join(groupby)
                idx_categories = obs_tidy_idx.cat.categories
            else:
                obs_tidy_idx = [adata.obs[group] for group in groupby] # keep as multiindex
                idx_categories = [x.cat.categories for x in obs_tidy_idx]

    obs_tidy.set_index(obs_tidy_idx, inplace=True)
    if gene_symbols is not None:
        # translate the column names to the symbol names
        obs_tidy.rename(
            columns={var_names[x]: symbols[x] for x in range(len(var_names))},
            inplace=True,
        )

    return idx_categories, obs_tidy


