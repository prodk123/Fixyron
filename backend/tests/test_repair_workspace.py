import os
import pytest
from unittest.mock import patch
from app.services.repair.workspace import create_repair_workspace, cleanup_repair_workspace

@patch("app.services.repair.workspace.clone_repository")
@patch("app.services.repair.workspace.uuid")
def test_create_repair_workspace(mock_uuid, mock_clone):
    mock_uuid.uuid4.return_value = "fake-uuid"
    
    workspace_path = create_repair_workspace("https://github.com/test/repo")
    
    assert workspace_path.endswith("fake-uuid")
    assert "/tmp/fixyron-repair-workspaces" in workspace_path
    mock_clone.assert_called_once_with("https://github.com/test/repo", workspace_path)

@patch("app.services.repair.workspace.shutil")
@patch("app.services.repair.workspace.os.path.exists")
def test_cleanup_repair_workspace(mock_exists, mock_shutil):
    mock_exists.return_value = True
    
    cleanup_repair_workspace("/tmp/fixyron-repair-workspaces/fake-uuid")
    
    mock_shutil.rmtree.assert_called_once_with("/tmp/fixyron-repair-workspaces/fake-uuid", ignore_errors=True)
