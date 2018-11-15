# coding: utf-8

"""
    simcore-service-storage API

    API definition for simcore-service-storage service  # noqa: E501

    OpenAPI spec version: 0.1.0
    Contact: support@simcore.io
    Generated by: https://openapi-generator.tech
"""


from __future__ import absolute_import

import unittest

import simcore_service_storage_sdk
from simcore_service_storage_sdk.api.users_api import UsersApi  # noqa: E501
from simcore_service_storage_sdk.rest import ApiException


class TestUsersApi(unittest.TestCase):
    """UsersApi unit test stubs"""

    def setUp(self):
        self.api = simcore_service_storage_sdk.api.users_api.UsersApi()  # noqa: E501

    def tearDown(self):
        pass

    def test_check_action_post(self):
        """Test case for check_action_post

        Test checkpoint to ask server to fail or echo back the transmitted data  # noqa: E501
        """
        pass

    def test_delete_file(self):
        """Test case for delete_file

        Deletes File  # noqa: E501
        """
        pass

    def test_download_file(self):
        """Test case for download_file

        Returns download link for requested file  # noqa: E501
        """
        pass

    def test_get_file_metadata(self):
        """Test case for get_file_metadata

        Get File Metadata  # noqa: E501
        """
        pass

    def test_get_files_metadata(self):
        """Test case for get_files_metadata

        Get Files Metadata  # noqa: E501
        """
        pass

    def test_get_storage_locations(self):
        """Test case for get_storage_locations

        Get available storage locations  # noqa: E501
        """
        pass

    def test_health_check(self):
        """Test case for health_check

        Service health-check endpoint  # noqa: E501
        """
        pass

    def test_update_file_meta_data(self):
        """Test case for update_file_meta_data

        Update File Metadata  # noqa: E501
        """
        pass

    def test_upload_file(self):
        """Test case for upload_file

        Returns upload link or performs copy operation to datcore  # noqa: E501
        """
        pass


if __name__ == '__main__':
    unittest.main()
