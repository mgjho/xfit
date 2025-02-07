import lmfit as lf
import numpy as np
import xarray as xr
from scipy.ndimage import gaussian_filter

from xrfit.base import DataArrayAccessor


def _get(
    data: xr.DataArray,
    params_name: str = "center",
    params_attr: str = "value",
):
    params = data.params.parse()
    return np.array(
        [
            getattr(params[key], params_attr)
            for key in params
            if key.endswith(params_name)
        ]
    )


def _set(
    data: xr.DataArray,
    params_value_new: xr.DataArray,
    params_name: str = "center",
    params_attr: str = "value",
):
    params = data.params.parse()
    pars = [key for key in params if key.endswith(params_name)]
    for i, par in enumerate(pars):
        setattr(params[par], params_attr, params_value_new[i])
    return data


def _set_bounds(
    modelresult: lf.model.ModelResult,
    bound_ratio: float = 0.1,
):
    for param_name, param_value in modelresult.params.items():
        param_min = param_value - bound_ratio * abs(param_value)
        param_max = param_value + bound_ratio * abs(param_value)
        modelresult.params.get(param_name).set(min=param_min, max=param_max)
    return modelresult


@xr.register_dataarray_accessor("params")
class ParamsAccessor(DataArrayAccessor):
    """
    For manipulating and accessing parameters.

    Methods
    -------
    __call__() -> xr.DataArray
        Applies a function to extract the 'params' attribute from the DataArray.

    smoothen(param_name: str = "center", sigma: int = 5) -> xr.DataArray
        Applies a Gaussian filter to smoothen the specified parameter.

    sort(target_param_name: str = "center", params_name: list | None = None) -> xr.DataArray
        Sorts the DataArray based on the specified target parameter and updates the specified parameters.

    get(params_name: str = "center", params_attr: str = "value") -> xr.DataArray
        Retrieves the specified parameter attribute from the DataArray.

    set(params_value_new: xr.DataArray, params_name: str = "center") -> xr.DataArray
        Sets the specified parameter in the DataArray to a new value.

    Attributes
    ----------
    _obj : xr.DataArray
        The xarray DataArray object to which this accessor is attached.
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
        bound_ratio: float = 0.1,
    ) -> xr.DataArray:
        return xr.apply_ufunc(
            _set_bounds,
            self._obj,
            kwargs={
                "bound_ratio": bound_ratio,
            },
            vectorize=True,
            dask="parallelized",
        )

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
        self._obj.params.set(param_smooth, param_name)
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
            self._obj.params.set(sorted_param, param_name)
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

    def set(
        self,
        params_value_new: xr.DataArray,
        params_name: str = "center",
        params_attr: str = "value",
    ) -> xr.DataArray:
        return xr.apply_ufunc(
            _set,
            self._obj,
            params_value_new,
            kwargs={
                "params_name": params_name,
                "params_attr": params_attr,
            },
            input_core_dims=[[], ["params_dim"]],
            vectorize=True,
        )
