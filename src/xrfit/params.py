import lmfit as lf
import numpy as np
import xarray as xr
from scipy.ndimage import gaussian_filter

from xrfit.base import DataArrayAccessor


def _get(
    data: lf.model.ModelResult,
    params_name: str = "center",
    params_attr: str = "value",
):
    params = data.params
    return np.array(
        [
            getattr(params[key], params_attr)
            for key in params
            if key.endswith(params_name)
        ]
    )


# TODO currently set value only.
def _assign(
    data: lf.model.ModelResult,
    params_value_new: xr.DataArray,
    params_name: str = "center",
):
    params = data.params
    pars = [key for key in params if key.endswith(params_name)]
    for i, par in enumerate(pars):
        data.params[par].set(value=params_value_new[i], min=-np.inf, max=np.inf)
    return data


def _set_bounds(
    modelresult: lf.model.ModelResult,
    bound_ratio: float = 0.1,
    bound_tol: float = 1e-3,
):
    for param_name, param_value in modelresult.params.items():
        if param_value.vary:
            param_min = param_value - bound_ratio * abs(param_value)
            param_max = param_value + bound_ratio * abs(param_value)
            if np.abs(param_value) <= bound_tol:
                param_min = -bound_tol
                param_max = bound_tol
            if param_value.min <= param_value:
                modelresult.params.get(param_name).set(min=param_min)
            if param_value.max >= param_value:
                modelresult.params.get(param_name).set(max=param_max)
    return modelresult


@xr.register_dataarray_accessor("params")
class ParamsAccessor(DataArrayAccessor):
    """
    Handle Parameter of the DataArray.

    Methods
    -------
    parse() -> xr.DataArray
        Parses the parameters from the DataArray.

    set_bounds(bound_ratio: float = 0.1) -> xr.DataArray
        Sets the bounds for the parameters based on a given ratio.

    smoothen(param_name: str = "center", sigma: int = 5) -> xr.DataArray
        Applies smoothing to the specified parameter.

    sort(target_param_name: str = "center", params_name: list | None = None) -> xr.DataArray
        Sorts the parameters based on the target parameter.

    get(params_name: str = "center", params_attr: str = "value") -> xr.DataArray
        Retrieves the specified parameter.

    set(params_value_new: xr.DataArray, params_name: str = "center", params_attr: str = "value") -> xr.DataArray
        Sets the specified parameter attribute to a new value.
    """

    def parse(
        self,
    ) -> xr.DataArray:
        return xr.apply_ufunc(
            lambda x: x.params,
            self._obj,
            vectorize=True,
            dask="parallelized",
            output_dtypes=[object],
        )

    def set_bounds(
        self,
        bound_ratio: float = 1.0,
        bound_tol: float = 1e-3,
        index_dict: dict | None = None,
    ) -> xr.DataArray:
        if index_dict is None:
            return xr.apply_ufunc(
                _set_bounds,
                self._obj,
                kwargs={
                    "bound_ratio": bound_ratio,
                    "bound_tol": bound_tol,
                },
                vectorize=True,
                dask="parallelized",
            )
        item = self._obj.isel(index_dict).item()
        index_dict = {k: self._obj.coords[k][v].item() for k, v in index_dict.items()}
        self._obj.loc[index_dict] = _set_bounds(
            item,
            bound_ratio=bound_ratio,
            bound_tol=bound_tol,
        )
        return self._obj

    def smoothen(
        self,
        param_name: str = "center",
        sigma: int = 5,
    ) -> xr.DataArray:
        param = self._obj.params.get(param_name)
        smoothing_sigma = [
            sigma if i < param.ndim - 1 else 0 for i in range(param.ndim)
        ]

        param_smooth = gaussian_filter(param, sigma=smoothing_sigma)
        self._obj.params.assign(param_smooth, param_name)
        return self._obj

    def sort(
        self,
        target_param_name: str = "center",
        params_name: list | None = None,
    ) -> xr.DataArray:
        if params_name is None:
            params_name = ["center"]
        param_to_sortby = self._obj.params.get(target_param_name)
        sorted_indices = param_to_sortby.argsort(axis=-1)
        for param_name in params_name:
            param = self._obj.params.get(param_name)
            sorted_param = param.isel(params_dim=sorted_indices)
            self._obj.params.assign(sorted_param, param_name)
        return self._obj

    def get(
        self,
        params_name: str = "center",
        params_attr: str = "value",
    ) -> xr.DataArray:
        return xr.apply_ufunc(
            _get,
            self._obj,
            kwargs={
                "params_name": params_name,
                "params_attr": params_attr,
            },
            input_core_dims=[[]],
            output_core_dims=[["params_dim"]],
            vectorize=True,
        )

    def assign(
        self,
        params_value_new: xr.DataArray,
        params_name: str = "center",
        # params_attr: str = "value",
    ) -> xr.DataArray:
        return xr.apply_ufunc(
            _assign,
            self._obj,
            params_value_new,
            kwargs={
                "params_name": params_name,
                # "params_attr": params_attr,
            },
            input_core_dims=[[], ["params_dim"]],
            vectorize=True,
        )
