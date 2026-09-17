import unittest
import asyncio
from unittest.mock import AsyncMock, patch
import httpx
from fastapi import HTTPException
import main_orchestrator as orch

class TestOrchestrator(unittest.IsolatedAsyncioTestCase):
    async def test_create_secret_invalid_hex(self):
        req = orch.SecretCreateRequest(id="test-1", secret="invalid_hex_string_xyz")
        with self.assertRaises(HTTPException) as ctx:
            await orch.create_secret(req)
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_create_secret_too_long(self):
        # 33 bytes = 66 hex characters
        req = orch.SecretCreateRequest(id="test-2", secret="aa" * 33)
        with self.assertRaises(HTTPException) as ctx:
            await orch.create_secret(req)
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_create_secret_quorum_failure(self):
        req = orch.SecretCreateRequest(id="test-3", secret="00" * 32)
        # Mock client to simulate all storage nodes being unreachable (ConnectError)
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")

        with patch.object(orch.app.state, "client", mock_client, create=True):
            with self.assertRaises(HTTPException) as ctx:
                await orch.create_secret(req)
            self.assertEqual(ctx.exception.status_code, 502)
            self.assertIn("Write quorum failed", ctx.exception.detail)

    async def test_create_secret_quorum_success(self):
        req = orch.SecretCreateRequest(id="test-4", secret="11" * 32)
        # 2 out of 3 succeed (HTTP 200), 1 fails (HTTP 500)
        mock_resp_ok = AsyncMock(status_code=200)
        mock_resp_fail = AsyncMock(status_code=500)
        mock_client = AsyncMock()
        mock_client.post.side_effect = [mock_resp_ok, mock_resp_ok, mock_resp_fail]

        with patch.object(orch.app.state, "client", mock_client, create=True):
            res = await orch.create_secret(req)
            self.assertEqual(res["quorum_achieved"], "2/3")

    async def test_reconstruct_secret_insufficient_shares(self):
        # Only 1 node responds
        from unittest.mock import MagicMock
        mock_resp_ok = MagicMock(status_code=200)
        mock_resp_ok.json.return_value = {"share": {"x": 1, "y_arr": [10]*32}}
        mock_client = AsyncMock()
        mock_client.get.side_effect = [mock_resp_ok, httpx.ConnectError("Down"), httpx.ConnectError("Down")]

        with patch.object(orch.app.state, "client", mock_client, create=True):
            with self.assertRaises(HTTPException) as ctx:
                await orch.reconstruct_secret("test-id")
            self.assertEqual(ctx.exception.status_code, 404)
            self.assertIn("Quorum not reached", ctx.exception.detail)

if __name__ == "__main__":
    unittest.main()
