#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
:mod:`calibraxis`
=================

Created by hbldh <henrik.blidh@nedomkull.com>
Created on 2016-04-25

Copyright (c) 2016, Nedomkull Mathematical Modeling AB.

"""

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

import six
import numpy as np

# Version information.
__version__ = '0.1.1.dev1'
version = __version__  # backwards compatibility name
version_info = (0, 1, 0, 'dev1')


class Calibraxis(object):
    """Calibration object, used for storing and applying the
    calibration parameters.

    :param int measuring_range: The operational range of the accelerometer,
        e.g. 8 in the case of +/- 8g range.
    :param int resolution: Number of bits the accelerometer returns data in.
        Used for calibrating against raw data.
    :param bool verbose: Print optimization progress data.

    """

    def __init__(self, measuring_range, resolution=None, verbose=False):
        self._points = []
        self._resolution = resolution
        self._range = measuring_range
        self._verbose = verbose

        # Accelerometer calibration parameters.
        self._acc_calibration_points = None
        self._acc_calibration_errors = None

        self.acc_bias_vector = None
        self.acc_scale_factor_matrix = None

    def add_points(self, points):
        """Add point(s) to the calibration procedure.

        :param list, tuple, numpy.ndarray points: The point(s) to add to the
            calibration point storage.

        """
        if isinstance(points, (list, tuple)):
            if len(points) > 0:
                if isinstance(points[0], (list, tuple, np.ndarray)):
                    # Multiple points sent as list of lists.
                    for p in points:
                        self._points.append(p)
                else:
                    # Assume single point sent in as list/tuple/array.
                    self._points.append(points)
            else:
                # Empty list/tuple. Skip.
                pass
        elif isinstance(points, np.ndarray):
            if points.ndim > 1:
                for p in points:
                    self._points.append(p.copy())
            elif points.ndim == 1:
                self._points.append(points.copy())

    def calibrate_accelerometer(self):
        """Perform calibration of accelerometer using stored points.

        Computes the Zero G levels, Sensitivity, Scale factor Matrix and the
        bias vector of a MEMS accelerometer.

        The procedure exploits the fact that, in static conditions, the
        modulus of the accelerometer output vector matches that of the
        gravity acceleration. The calibration model incorporates the bias
        and scale factor for each axis and the cross-axis symmetrical
        factors. The parameters are computed through Gauss-Newton
        nonlinear optimization.

        The mathematical model used is  A = M(V - B)
        where M and B are scale factor matrix and bias vector respectively.

        M = [ Mxx Mxy Mxz; Myx Myy Myz; Mzx Mzy Mzz ]
        where  Mxy = Myx; Myz = Mzy; Mxz = Mzx;
        B = [ Bx; By; Bz ]

        The diagonal elements of M represent the scale factors along the
        three axes, whereas the other elements of M are called cross-axis
        factors. These terms allow describing both the axes’ misalignment
        and the crosstalk effect between different channels caused
        by the sensor electronics. In an ideal world, M = 1; B = 0

        Reference:
        Iuri Frosio, Federico Pedersini, N. Alberto Borghese
        "Autocalibration of MEMS Accelerometers"
        IEEE TRANSACTIONS ON INSTRUMENTATION AND MEASUREMENT,
        VOL. 58, NO. 6, JUNE 2009

        This is a Python reimplementation of the Matlab routines found at
        `Matlab File Central <http://se.mathworks.com/matlabcentral/fileexchange/
        33252-mems-accelerometer-calibration-using-gauss-newton-method>`_.

        """
        points = np.array(self._points)
        self._perform_accelerometer_calibration_optimisation(points)

    def _perform_accelerometer_calibration_optimisation(self, points):
        """Perform the Gauss-Newton optimisation for parameters."""
        nbr_points = len(points)
        if nbr_points < 9:
            raise ValueError(
                'Need at least 9 measurements for the calibration procedure!')

        def error_function(M_mat, b_vec, y):
            """Optimisation error function for a point.

            :param numpy.ndarray M_mat: The scale factor matrix
                of this iteration.
            :param numpy.ndarray b_vec: The zero-g offset vector
                of this iteration.
            :param numpy.ndarray y: The point ot estimate error for.
            :return: The square sum of the error of this point.
            :rtype: float

            """
            return float(np.sum((M_mat.dot((y - b_vec)) ** 2)) - 1)

        def calculate_jacobian(M_mat, b_vec, point):
            """Calculate the Jacobian for a point.

            :param numpy.ndarray M_mat: The scale factor matrix
                of this iteration.
            :param numpy.ndarray b_vec: The zero-g offset vector
                of this iteration.
            :param numpy.ndarray y: The point ot estimate error for.
            :return: The square sum of the error of this point.
            :rtype: float

            """
            jac = np.zeros((9,), 'float')

            jac[0] = 2 * (b_vec[0] - point[0]) * (
                M_mat[0, 0] * (b_vec[0] - point[0]) + M_mat[0, 1] * (
                b_vec[1] - point[1]) + M_mat[0, 2] * (
                    b_vec[2] - point[2]))
            jac[1] = 2 * (b_vec[1] - point[1]) * (
                M_mat[0, 0] * (b_vec[0] - point[0]) + M_mat[0, 1] * (
                b_vec[1] - point[1]) + M_mat[0, 2] * (
                    b_vec[2] - point[2])) + 2 * (b_vec[0] - point[0]) * (
                M_mat[0, 1] * (b_vec[0] - point[0]) + M_mat[1, 1] * (
                b_vec[1] - point[1]) + M_mat[1, 2] * (
                    b_vec[2] - point[2]))
            jac[2] = 2 * (b_vec[0] - point[0]) * (
                M_mat[0, 2] * (b_vec[0] - point[0]) + M_mat[1, 2] * (
                b_vec[1] - point[1]) + M_mat[2, 2] * (
                    b_vec[2] - point[2])) + 2 * (b_vec[2] - point[2]) * (
                M_mat[0, 0] * (b_vec[0] - point[0]) + M_mat[0, 1] * (
                b_vec[1] - point[1]) + M_mat[0, 2] * (
                    b_vec[2] - point[2]))
            jac[3] = 2 * (b_vec[1] - point[1]) * (
                M_mat[0, 1] * (b_vec[0] - point[0]) + M_mat[1, 1] * (
                b_vec[1] - point[1]) + M_mat[1, 2] * (
                    b_vec[2] - point[2]))
            jac[4] = 2 * (b_vec[1] - point[1]) * (
                M_mat[0, 2] * (b_vec[0] - point[0]) + M_mat[1, 2] * (
                b_vec[1] - point[1]) + M_mat[2, 2] * (
                    b_vec[2] - point[2])) + 2 * (b_vec[2] - point[2]) * (
                M_mat[0, 1] * (b_vec[0] - point[0]) + M_mat[1, 1] * (
                b_vec[1] - point[1]) + M_mat[1, 2] * (
                    b_vec[2] - point[2]))
            jac[5] = 2 * (b_vec[2] - point[2]) * (
                M_mat[0, 2] * (b_vec[0] - point[0]) + M_mat[1, 2] * (
                b_vec[1] - point[1]) + M_mat[2, 2] * (
                    b_vec[2] - point[2]))
            jac[6] = 2 * M_mat[0, 0] * (
                M_mat[0, 0] * (b_vec[0] - point[0]) + M_mat[0, 1] * (
                b_vec[1] - point[1]) + M_mat[0, 2] * (
                    b_vec[2] - point[2])) + 2 * M_mat[0, 1] * (
                M_mat[0, 1] * (b_vec[0] - point[0]) + M_mat[1, 1] * (
                b_vec[1] - point[1]) + M_mat[1, 2] * (
                    b_vec[2] - point[2])) + 2 * M_mat[0, 2] * (
                M_mat[0, 2] * (b_vec[0] - point[0]) + M_mat[1, 2] * (
                b_vec[1] - point[1]) + M_mat[2, 2] * (
                    b_vec[2] - point[2]))
            jac[7] = 2 * M_mat[0, 1] * (
                M_mat[0, 0] * (b_vec[0] - point[0]) + M_mat[0, 1] * (
                b_vec[1] - point[1]) + M_mat[0, 2] * (
                    b_vec[2] - point[2])) + 2 * M_mat[1, 1] * (
                M_mat[0, 1] * (b_vec[0] - point[0]) + M_mat[1, 1] * (
                b_vec[1] - point[1]) + M_mat[1, 2] * (
                    b_vec[2] - point[2])) + 2 * M_mat[1, 2] * (
                M_mat[0, 2] * (b_vec[0] - point[0]) + M_mat[1, 2] * (
                b_vec[1] - point[1]) + M_mat[2, 2] * (
                    b_vec[2] - point[2]))
            jac[8] = 2 * M_mat[0, 2] * (
                M_mat[0, 0] * (b_vec[0] - point[0]) + M_mat[0, 1] * (
                b_vec[1] - point[1]) + M_mat[0, 2] * (
                    b_vec[2] - point[2])) + 2 * M_mat[1, 2] * (
                M_mat[0, 1] * (b_vec[0] - point[0]) + M_mat[1, 1] * (
                b_vec[1] - point[1]) + M_mat[1, 2] * (
                    b_vec[2] - point[2])) + 2 * M_mat[2, 2] * (
                M_mat[0, 2] * (b_vec[0] - point[0]) + M_mat[1, 2] * (
                b_vec[1] - point[1]) + M_mat[2, 2] * (
                    b_vec[2] - point[2]))

            return jac

        def optvec_to_M_and_b(v):
            """
            Convenience method for moving between optimisation
            vector and correct lin.alg. formulation.
            """
            return (np.array([[v[0], v[1], v[2]],
                              [v[1], v[3], v[4]],
                              [v[2], v[4], v[5]]]),
                    v[6:].copy())

        gain = 1  # Damping Gain - Start with 1
        damping = 0.01    # Damping parameter - has to be less than 1.
        tolerance = 1e-12
        R_prior = 100000
        self._acc_calibration_errors = []
        nbr_iterations = 200

        # Initial Guess values of M and b.
        if self.acc_bias_vector is not None:
            # Recalibration using prior optimization results.
            x = np.array([self.acc_scale_factor_matrix[0, 0],
                          self.acc_scale_factor_matrix[0, 1],
                          self.acc_scale_factor_matrix[0, 2],
                          self.acc_scale_factor_matrix[1, 1],
                          self.acc_scale_factor_matrix[1, 2],
                          self.acc_scale_factor_matrix[2, 2],
                          self.acc_bias_vector[0],
                          self.acc_bias_vector[1],
                          self.acc_bias_vector[2]])
        else:
            # Fresh calibration.
            sensitivity = 1 / np.sqrt((points ** 2).sum(axis=1)).mean()
            x = np.array([sensitivity, 0.0, 0.0,
                          sensitivity, 0.0, sensitivity,
                          0.0, 0.0, 0.0])
        last_x = x.copy()

        # Residuals vector
        R = np.zeros((nbr_points, ), 'float')

        # Jacobian matrix
        J = np.zeros((nbr_points, 9), 'float')

        for n in six.moves.range(nbr_iterations):
            # Calculate the Jacobian and error for each point.
            M, b = optvec_to_M_and_b(x)
            for i in six.moves.range(nbr_points):
                R[i] = error_function(M, b, points[i, :])
                J[i, :] = calculate_jacobian(M, b, points[i, :])

            # Calculate Hessian, Gain matrix and apply it to solution vector.
            H = np.linalg.inv(J.T.dot(J))
            D = J.T.dot(R).T
            x -= gain * (D.dot(H)).T
            R_post = np.linalg.norm(R)
            if self._verbose:
                print("{0}: {1} ({2})".format(
                    n, R_post, ", ".join(["{0:0.9g}".format(v) for v in x])))

            # This is to make sure that the error is
            # decreasing with every iteration.
            if R_post <= R_prior:
                gain -= damping * gain
            else:
                gain *= damping

            # Iterations are stopped when the following
            # convergence criteria is satisfied.
            if abs(max(2 * (x - last_x) / (x + last_x))) <= tolerance:
                self.acc_scale_factor_matrix, self.acc_bias_vector = \
                    optvec_to_M_and_b(x)
                break

            last_x = x.copy()
            R_prior = R_post
            self._acc_calibration_errors.append(R_post)

    def apply(self, acc_values):
        """Apply the calibration scale matrix and bias to accelerometer values.

        :param list, tuple, numpy.ndaray acc_values: The accelerometer data.
        :return: The transformed accelerometer values.
        :rtype: tuple

        """
        converted_g_values = self.acc_scale_factor_matrix.dot(
            np.array(acc_values) - self.acc_bias_vector)
        return tuple(converted_g_values.tolist())

    def batch_apply(self, acc_values):
        """Apply the calibration scale matrix and bias to an array of
        accelerometer data

        Assumes that the input is either a list or tuple containing three
        element lists, tuples or arrays or a [N x 3] NumPy array.

        :param list, tuple, numpy.ndaray acc_values: The accelerometer data.
        :return: The transformed accelerometer values.
        :rtype: list

        """
        return [self.apply(a) for a in acc_values]
