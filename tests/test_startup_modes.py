import time
import unittest
import tempfile
import os

import jwt

from mltf_gateway.executors.ssam_executor import (
    ReloadableToken,
    SSAMExecutor,
    get_jwt_expiration,
)


def make_token(expiry_offset_seconds: int) -> str:
    """Create a test JWT that expires in `expiry_offset_seconds`."""
    return jwt.encode(
        {
            "sub": "test-user",
            "exp": int(time.time()) + expiry_offset_seconds,
            "iss": "test-issuer",
        },
        "test-secret",
        algorithm="HS256",
    )


class ReloadableTokenTest(unittest.TestCase):
    def test_valid_env_token(self):
        token = make_token(3600)
        rt = ReloadableToken(token=token)
        self.assertTrue(rt.valid)
        self.assertEqual(rt.token, token)

    def test_invalid_env_token(self):
        rt = ReloadableToken(token="not-a-real-jwt")
        self.assertFalse(rt.valid)
        self.assertEqual(rt.token, "not-a-real-jwt")

    def test_expired_env_token(self):
        token = make_token(-3600)
        rt = ReloadableToken(token=token)
        self.assertFalse(rt.valid)

    def test_valid_file_token(self):
        token = make_token(3600)
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(token)
            f.flush()
            f.close()
        rt = ReloadableToken(token_path=f.name)
        self.assertTrue(rt.valid)
        os.remove(f.name)

    def test_invalid_file_token(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("not-a-real-jwt")
            f.flush()
            f.close()
        rt = ReloadableToken(token_path=f.name)
        self.assertFalse(rt.valid)
        os.remove(f.name)

    def test_expired_file_token(self):
        token = make_token(-3600)
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(token)
            f.flush()
            f.close()
        rt = ReloadableToken(token_path=f.name)
        self.assertFalse(rt.valid)
        os.remove(f.name)

    def test_missing_file(self):
        """Missing file -> token remains None, valid=False (degraded mode)."""
        rt = ReloadableToken(token_path="/nonexistent/path")
        self.assertFalse(rt.valid)
        self.assertIsNone(rt.token)


class SSAMExecutorStartupModeTest(unittest.TestCase):
    """Verify the three startup modes described in PLAN.md."""

    def _cleanup_env(self):
        for key in [
            "AUTH_TOKEN",
            "SLURM_TOKEN",
            "AUTH_TOKEN_PATH",
            "SLURM_TOKEN_PATH",
        ]:
            os.environ.pop(key, None)

    def setUp(self):
        self._cleanup_env()

    def tearDown(self):
        self._cleanup_env()

    def test_case_a_valid_tokens_start_normal(self):
        """Valid tokens in env vars -> degraded=False."""
        auth = make_token(3600)
        slurm = make_token(3600)
        os.environ["AUTH_TOKEN"] = auth
        os.environ["SLURM_TOKEN"] = slurm

        executor = SSAMExecutor()
        self.assertFalse(executor.degraded)

    def test_case_b_invalid_tokens_with_paths_degraded(self):
        """Invalid tokens loaded from files -> degraded=True, no exception."""
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("bad-auth-jwt")
            f.flush()
            f.close()
            auth_path = f.name
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("bad-slurm-jwt")
            f.flush()
            f.close()
            slurm_path = f.name
        os.environ["AUTH_TOKEN_PATH"] = auth_path
        os.environ["SLURM_TOKEN_PATH"] = slurm_path

        executor = SSAMExecutor()
        self.assertTrue(executor.degraded)
        os.remove(auth_path)
        os.remove(slurm_path)

    def test_case_c_invalid_tokens_no_path_exit_early(self):
        """Invalid token passed directly with no path -> ValueError."""
        os.environ["AUTH_TOKEN"] = "not-a-real-jwt"
        os.environ["SLURM_TOKEN"] = "not-a-real-jwt"

        with self.assertRaises(ValueError):
            SSAMExecutor()

    def test_case_c_one_invalid_no_path(self):
        """Only auth invalid with no path -> ValueError."""
        valid = make_token(3600)
        os.environ["AUTH_TOKEN"] = "not-a-real-jwt"
        os.environ["SLURM_TOKEN"] = valid

        with self.assertRaises(ValueError):
            SSAMExecutor()

    def test_case_b_mixed_one_valid_one_invalid(self):
        """Auth valid, slurm invalid from path -> degraded=True."""
        valid = make_token(3600)
        os.environ["AUTH_TOKEN"] = valid
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("bad-slurm-jwt")
            f.flush()
            f.close()
            slurm_path = f.name
        os.environ["SLURM_TOKEN_PATH"] = slurm_path

        executor = SSAMExecutor()
        self.assertTrue(executor.degraded)
        os.remove(slurm_path)


if __name__ == "__main__":
    unittest.main()
