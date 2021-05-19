import numpy as np

from abc import ABC

from typing import Optional
from filterpy.kalman import KalmanFilter as FpKalmanFilter

from .filtering_model import FilteringModel
from ..timeseries import TimeSeries
from ..utils.utils import raise_if_not


class KalmanFilter(FilteringModel, ABC):
    def __init__(
            self, 
            dim_x: int = 1,
            x_init: Optional[np.array] = None,
            P: Optional[np.array] = None,
            Q: Optional[np.array] = None,
            R: Optional[np.array] = None,
            H: Optional[np.array] = None,
            F: Optional[np.array] = None,
            kf: Optional[FpKalmanFilter] = None
            ):
        """ KalmanFilter model
        This model implements a Kalman filter over a time series (without control signal).

        The key method is `KalmanFilter.filter()`.
        It considers the provided time series as containing (possibly noisy) observations z obtained from a
        (possibly noisy) linear dynamical system with hidden state x. The function `filter(series)` returns a new
        `TimeSeries` containing the mean values of the state x, as inferred by the Kalman filter from
        sequentially observing z from `series`.
        Depending on the use case, this can be used to de-noise a series or infer the underlying hidden state of the
        data generating process (assuming notably that the dynamical system generating the data is known, as captured
        by the `F` matrix.).

        This implementation wraps around filterpy.kalman.KalmanFilter, so more information the parameters can be found
        here: https://filterpy.readthedocs.io/en/latest/kalman/KalmanFilter.html

        The dimensionality of the measurements z is automatically inferred upon calling `filter()`.
        This implementation doesn't include control signal.

        Parameters
        ----------
        dim_x : int
            Size of the Kalman filter state vector. It determines the dimensionality of the `TimeSeries`
            returned by the `filter()` function.
        x_init : ndarray (dim_x, 1), default: [0, 0, ..., 0]
            Initial state; will be updated at each time step.
        P : ndarray (dim_x, dim_x), default: identity matrix
            initial covariance matrix; will be update at each time step
        Q : ndarray (dim_x, dim_x), default: identity matrix
            Process noise covariance matrix
        R : ndarray (dim_z, dim_z), default: identity matrix
            Measurement noise covariance matrix. `dim_z` must match the dimensionality (width) of the `TimeSeries`
            used with `filter()`.
        H : ndarray (dim_z, dim_x), default: all-ones matrix
            measurement function; describes how the measurement z is obtained from the state vector x
        F : ndarray (dim_x, dim_x), default: identity matrix
            State transition matrix; describes how the state evolves from one time step to the next
            in the underlying dynamical system.
        kf : filterpy.kalman.KalmanFilter
            Optionally, an instance of `filterpy.kalman.KalmanFilter`.
            If this is provided, the other parameters are ignored. The various dimensionality in the filter
            must match those in the `TimeSeries` used when calling `filter()`.
        """
        super().__init__()
        if kf is None:
            self.dim_x = dim_x
            self.x_init = x_init if x_init is not None else np.zeros(self.dim_x,)
            self.P = P if P is not None else np.eye(self.dim_x)
            self.Q = Q if Q is not None else np.eye(self.dim_x)
            self.R = R
            self.H = H
            self.F = F if F is not None else np.eye(self.dim_x)
            self.kf = None
        else:
            self.kf = kf

    def __str__(self):
        return 'KalmanFilter(dim_x={})'.format(self.dim_x)

    def filter(self, series: TimeSeries):
        """
        Sequentially applies the Kalman filter on the provided series of observations.

        Parameters
        ----------
        series : TimeSeries
            The series of observations used to infer the state values according to the specified Kalman process

        Returns
        -------
        TimeSeries
            A `TimeSeries` of state values, of dimension `dim_x`.
        """

        dim_z = series.width

        if self.kf is None:
            kf = FpKalmanFilter(dim_x=self.dim_x, dim_z=dim_z)
            kf.x = self.x_init
            kf.P = self.P
            kf.Q = self.Q
            kf.R = self.R if self.R is not None else np.eye(dim_z)
            kf.H = self.H if self.H is not None else np.ones((dim_z, self.dim_x))
            kf.F = self.F
            self.kf = kf
        else:
            raise_if_not(dim_z == self.kf.dim_z, 'The provided TimeSeries dimensionality does not match '
                                                 'the filter observation dimensionality dim_z.')

        super().filter(series)
        values = series.values(copy=False)
        filtered_values = np.zeros((len(values), self.dim_x))  # mean values
        # covariances = ...                               # covariance matrices; TODO
        for i in range(len(values)):
            obs = values[i, :]
            self.kf.predict()
            self.kf.update(obs)
            filtered_values[i, :] = self.kf.x.reshape(self.dim_x,)
            # covariances[i] = self.kf.P  # covariance matrix estimate for the state TODO

        return TimeSeries.from_times_and_values(series.time_index(), filtered_values)
