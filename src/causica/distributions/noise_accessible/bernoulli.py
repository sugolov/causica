import torch
import torch.distributions as td
import torch.nn.functional as F

from causica.distributions.noise_accessible.noise_accessible import NoiseAccessible


class NoiseAccessibleBernoulli(td.Bernoulli, NoiseAccessible):
    def __init__(self, delta_logits: torch.Tensor, base_logits: torch.Tensor):
        """
        A Bernoulli distribution with parameters defined by base_logits and x_hat (predictions for noiseless value).

        Args:
            delta_logits: Tensor with shape sample_shape + batch_shape. These are the predicted values.
            base_logits: Tensor with shape batch_shape
        """
        self.delta_logits = delta_logits
        super().__init__(logits=base_logits + delta_logits, validate_args=False)

    def sample_to_noise(self, samples: torch.Tensor) -> torch.Tensor:
        """
        Transform from the sample observations to corresponding noise variables.

        This will draw from the noise posterior given the observations

        A posterior sample of the Gumbel noise random variables given observation x and probabilities `self.base_logits + logit_deltas`.

        This methodology is described in https://arxiv.org/pdf/1905.05824.pdf.
        See https://cmaddis.github.io/gumbel-machinery for derivation of Gumbel posteriors.
        For a derivation of this exact algorithm using softplus, see https://www.overleaf.com/8628339373sxjmtvyxcqnx.

        Args:
            samples: Tensor of shape sample_shape + batch_shape + event_shape
        Returns:
            The generated samples with shape sample_shape + batch_shape + event_shape
        """
        assert (
            samples.shape == self.delta_logits.shape
        ), "The shape of the input does not match the shape of the logit_deltas"
        device = self.delta_logits.device
        dist = td.Gumbel(torch.tensor(0.0, device=device), torch.tensor(1.0, device=device))
        diff_sample = dist.sample(samples.shape) - dist.sample(samples.shape)  # sample_shape + batch_shape
        neg_log_prob_non_sampled = F.softplus(self.logits * samples - self.logits * (1 - samples))
        positive_sample = F.softplus(diff_sample + neg_log_prob_non_sampled)
        return positive_sample * samples - positive_sample * (1 - samples) - self.delta_logits

    def noise_to_sample(self, noise: torch.Tensor) -> torch.Tensor:
        """
        Generate samples using the given exogenous noise.

        Args:
            noise: noise variable with shape sample_shape + batch_shape.
        Returns:
            The generated samples with shape sample_shape + batch_shape + event_shape
        """
        return ((self.delta_logits + noise) > 0).float()