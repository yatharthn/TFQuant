# Lint as: python3
# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for CIR."""

from absl.testing import parameterized
import numpy as np
import tensorflow.compat.v2 as tf

import tf_quant_finance as tff
from tensorflow.python.framework import test_util  # pylint: disable=g-direct-tensorflow-import
from tf_quant_finance.math import random_ops as random


@test_util.run_all_in_graph_and_eager_modes
class CirTest(parameterized.TestCase, tf.test.TestCase):

  @parameterized.named_parameters(
      {
          "testcase_name": "SinglePrecision",
          "dtype": np.float32,
      }, {
          "testcase_name": "DoublePrecision",
          "dtype": np.float64,
      })
  def test_drift_and_volatility(self, dtype):
    """Tests CIR drift and volatility functions."""
    theta = 0.04
    mean_reversion = 0.6
    sigma = 0.1
    process = tff.experimental.cir.CirModel(
        theta=theta,
        mean_reversion=mean_reversion,
        sigma=sigma,
        dtype=np.float64)
    drift_fn = process.drift_fn()
    volatility_fn = process.volatility_fn()
    state = np.array([[1.], [3.], [5.]], dtype=dtype)
    with self.subTest("Drift"):
      drift = drift_fn(0.2, state)
      expected_drift = theta - mean_reversion * state
      self.assertAllClose(expected_drift, drift, atol=1e-7, rtol=1e-7)
    with self.subTest("Volatility"):
      vol = volatility_fn(0.2, state)
      expected_vol = np.expand_dims(sigma * np.sqrt(state), axis=-1)
      self.assertAllClose(expected_vol, vol, atol=1e-7, rtol=1e-7)

  @parameterized.named_parameters(
      {
          "testcase_name": "InitialStateNotCloseToMean",
          "initial_state": 5.1,
          "times": np.arange(100.0, 140, 2.0)
      }, {
          "testcase_name": "InitialStateCloseToMean",
          "initial_state": 0.0,
          "times": np.arange(100.0, 140, 2.0)
      })
  def test_sample_paths_long_term_mean(self, initial_state, times):
    """Testing long term mean."""
    # Construct CIR model
    (theta, mean_reversion, sigma, _, num_samples, _, random_type, seed,
     dtype) = self.get_default_params()
    process = tff.experimental.cir.CirModel(
        theta=theta, mean_reversion=mean_reversion, sigma=sigma, dtype=dtype)
    # Act
    samples = process.sample_paths(
        times=times,
        initial_state=initial_state,
        num_samples=num_samples,
        random_type=random_type,
        seed=seed)
    # Assert
    self.verify_samples(
        process,
        samples,
        theta,
        mean_reversion,
        initial_state,
        num_samples,
        times,
        dtype,
        compare_with_euler=False,
        compare_long_term=True)

  @parameterized.named_parameters(
      {
          "testcase_name": "sigma**2=a/2",
          "sigma_coef": 0.5,
      }, {
          "testcase_name": "sigma**2=2*a",
          "sigma_coef": 2,
      }, {
          "testcase_name": "sigma**2=8*a",
          "sigma_coef": 8,
      })
  def test_sample_paths_long_term_mean_different_sigmas(self, sigma_coef):
    """Testing long term mean."""
    # Construct CIR model
    (theta, mean_reversion, _, initial_state, num_samples, _, random_type, seed,
     dtype) = self.get_default_params()
    times = np.arange(100.0, 140.0, 2.0)
    sigma = theta * sigma_coef
    process = tff.experimental.cir.CirModel(
        theta=theta, mean_reversion=mean_reversion, sigma=sigma, dtype=dtype)
    # Act
    samples = process.sample_paths(
        times=times,
        initial_state=initial_state,
        num_samples=num_samples,
        random_type=random_type,
        seed=seed)
    # Assert
    self.verify_samples(
        process,
        samples,
        theta,
        mean_reversion,
        initial_state,
        num_samples,
        times,
        dtype,
        compare_with_euler=False,
        compare_long_term=True)

  def test_sample_paths_mean_reversion_is_tensor(self):
    """`mean_reversion` is Tensor."""
    # Construct CIR model
    (theta, _, sigma, initial_state, num_samples, times, random_type, seed,
     dtype) = self.get_default_params()
    mean_reversion = tf.constant(0.5, dtype=dtype)
    process = tff.experimental.cir.CirModel(
        theta=theta, mean_reversion=mean_reversion, sigma=sigma, dtype=dtype)
    # Act
    samples = process.sample_paths(
        times=times,
        initial_state=initial_state,
        num_samples=num_samples,
        random_type=random_type,
        seed=seed)
    # Assert
    self.verify_samples(process, samples, theta, mean_reversion, initial_state,
                        num_samples, times, dtype)

  def test_sample_paths_mean_reversion_is_zero(self):
    """When `mean_reversion` is zero `zeta` returns `t`."""
    # Construct CIR model
    (theta, _, sigma, initial_state, num_samples, times, random_type, seed,
     dtype) = self.get_default_params()
    mean_reversion = 0.0
    process = tff.experimental.cir.CirModel(
        theta=theta, mean_reversion=mean_reversion, sigma=sigma, dtype=dtype)
    # Act
    samples = process.sample_paths(
        times=times,
        initial_state=initial_state,
        num_samples=num_samples,
        random_type=random_type,
        seed=seed)
    # Assert
    with self.subTest("dType"):
      self.assertDTypeEqual(samples, dtype)
    with self.subTest("GreaterEqualThanZero"):
      self.assertAllGreaterEqual(samples, 0.0)

  @parameterized.named_parameters(
      {
          "testcase_name": "dtype=float64",
          "dtype": np.float64,
      },
      {
          "testcase_name": "dtype=float32",
          "dtype": np.float32,
      },
      {
          "testcase_name": "dtype=None",
          "dtype": None,
      },
  )
  def test_sample_paths_different_dtypes(self, dtype):
    """`initial_state's` type is not equal to `dtype` provided to constructor."""
    # Construct CIR model
    (theta, mean_reversion, sigma, initial_state, num_samples, times,
     random_type, seed, _) = self.get_default_params()
    process = tff.experimental.cir.CirModel(
        theta=theta, mean_reversion=mean_reversion, sigma=sigma, dtype=dtype)
    # Act
    samples = process.sample_paths(
        times=times,
        num_samples=num_samples,
        initial_state=initial_state,
        random_type=random_type,
        seed=seed)
    # Assert
    self.verify_samples(process, samples, theta, mean_reversion, initial_state,
                        num_samples, times, dtype or np.float32)

  def test_sample_paths_initial_state_is_none(self):
    """`initial_state` is none."""
    # Construct CIR model
    (theta, mean_reversion, sigma, _, num_samples, times, random_type, seed,
     dtype) = self.get_default_params()
    process = tff.experimental.cir.CirModel(
        theta=theta, mean_reversion=mean_reversion, sigma=sigma, dtype=dtype)
    # Act
    samples = process.sample_paths(
        times=times,
        num_samples=num_samples,
        random_type=random_type,
        seed=seed)
    # Assert
    self.verify_samples(
        process=process,
        samples=samples,
        theta=theta,
        mean_reversion=mean_reversion,
        initial_state=1.0,  # `initial_state` default value in CIR is 1.0
        num_samples=num_samples,
        times=times,
        dtype=dtype)

  def test_sample_paths_seed_is_none(self):
    """`seed` is none."""
    # Construct CIR model
    (theta, mean_reversion, sigma, initial_state, num_samples, times,
     random_type, _, dtype) = self.get_default_params()
    process = tff.experimental.cir.CirModel(
        theta=theta, mean_reversion=mean_reversion, sigma=sigma, dtype=dtype)
    # Act
    with self.assertRaises(ValueError):
      process.sample_paths(
          times=times,
          num_samples=num_samples,
          initial_state=initial_state,
          random_type=random_type)

  def test_sample_paths_not_supported_random_type(self):
    """`random_type` is not `STATELESS` or `PSEUDO`."""
    # Construct CIR model
    (theta, mean_reversion, sigma, initial_state, num_samples, times, _, seed,
     dtype) = self.get_default_params()
    process = tff.experimental.cir.CirModel(
        theta=theta, mean_reversion=mean_reversion, sigma=sigma, dtype=dtype)
    # Act
    with self.assertRaises(ValueError):
      process.sample_paths(
          times=times,
          num_samples=num_samples,
          initial_state=initial_state,
          random_type=random.RandomType.HALTON,
          seed=seed)

  def verify_samples(self,
                     process,
                     samples,
                     theta,
                     mean_reversion,
                     initial_state,
                     num_samples,
                     times,
                     dtype,
                     compare_long_term=False,
                     compare_with_euler=True,
                     long_term_atol=5e-2,
                     long_term_rtol=5e-2,
                     euler_time_step=0.02,
                     euler_atol=1e-2,
                     euler_rtol=1e-2):
    dim = 1
    with self.subTest("Mean"):
      if compare_long_term:
        with self.subTest("LongTermMean"):
          long_term_mean, _ = self.get_mean_and_var(samples, axis=1)
          expected_long_term_mean = np.ones([num_samples
                                            ]) * theta / mean_reversion
          # In the infinite limit, the mean must converge
          # to 'theta / mean_reversion'
          self.assertAllClose(
              expected_long_term_mean,
              long_term_mean,
              atol=long_term_atol,
              rtol=long_term_rtol)

      if compare_with_euler:
        euler_samples = tff.models.euler_sampling.sample(
            dim=dim,
            drift_fn=process.drift_fn(),
            volatility_fn=process.volatility_fn(),
            times=times,
            time_step=euler_time_step,
            num_samples=num_samples,
            initial_state=initial_state,
            dtype=dtype,
            random_type=random.RandomType.STATELESS,
            seed=[1, 5])
        mean, var = self.get_mean_and_var(samples)
        euler_mean, euler_var = self.get_mean_and_var(euler_samples)
        with self.subTest("EulerMean"):
          self.assertAllClose(
              euler_mean, mean, atol=euler_atol, rtol=euler_rtol)
        with self.subTest("EulerVar"):
          self.assertAllClose(euler_var, var, atol=euler_atol, rtol=euler_rtol)
        with self.subTest("EulerShape"):
          self.assertEqual(euler_samples.shape, samples.shape)
    with self.subTest("dType"):
      self.assertDTypeEqual(samples, dtype)
    with self.subTest("GreaterEqualThanZero"):
      self.assertAllGreaterEqual(samples, 0.0)
    with self.subTest("Shape"):
      self.assertEqual([num_samples, times.shape[0], dim], samples.shape)

  def get_mean_and_var(self, samples, axis=0):
    """samples: A `Tensor`s of shape [num_samples, num_times, 1]."""
    # Shape [num_samples, num_times]
    samples_np = self.evaluate(samples[..., -1])
    # Reduce along samples/times dimension
    # Shape [num_times] if axis=0, shape [num_samples] if axis=1
    mean = np.mean(samples_np, axis=axis)
    var = np.var(samples_np, axis=axis)
    return mean, var

  def get_default_params(self):
    theta = 0.02
    mean_reversion = 0.5
    sigma = 0.1
    initial_state = 10.0
    num_samples = 10_000
    times = np.arange(0.0, 1.0, 0.1)
    random_type = random.RandomType.STATELESS
    seed = [1, 5]
    dtype = np.float64
    return (theta, mean_reversion, sigma, initial_state, num_samples, times,
            random_type, seed, dtype)


if __name__ == "__main__":
  tf.test.main()
