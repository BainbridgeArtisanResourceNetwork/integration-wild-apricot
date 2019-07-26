r"""
This module provides set of classes for working with WildApricot public API v2.
Public API documentation can be found here: http://help.wildapricot.com/display/DOC/API+Version+2

Example:
    api = WaApi.WaApiClient()
    api.authenticate_with_contact_credentials("admin@youraccount.com", "your_password")
    accounts = api.execute_request("/v2/accounts")
    for account in accounts:
        print(account.PrimaryDomainName)
"""

__author__ = 'dsmirnov@wildapricot.com'

import datetime
import urllib.request
import urllib.response
import urllib.error
import urllib.parse
import json
import pickle
import logging
import base64


class WaApiClient(object):
    """Wild apricot API client."""
    auth_endpoint = "https://oauth.wildapricot.org/auth/token"
    api_endpoint = "https://api.wildapricot.org"
    _token = None
    client_id = None
    client_secret = None

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret

    def authenticate_with_apikey(self, api_key, scope=None):
        """perform authentication by api key and store result for execute_request method

        api_key -- secret api key from account settings
        scope -- optional scope of authentication request. If None full list of API scopes will be used.
        """
        logging.info("Authenticating with WildApricot (scope=%s)", scope)
        scope = "auto" if scope is None else scope
        data = {
            "grant_type": "client_credentials",
            "scope": scope
        }
        encoded_data = urllib.parse.urlencode(data).encode()
        request = urllib.request.Request(self.auth_endpoint, encoded_data, method="POST")
        request.add_header("ContentType", "application/x-www-form-urlencoded")
        request.add_header("Authorization", 'Basic ' + base64.standard_b64encode(('APIKEY:' + api_key).encode()).decode())
        response = urllib.request.urlopen(request)
        self._token = WaApiClient._parse_response(response)
        self._token.retrieved_at = datetime.datetime.now()
        self._accountId = self._token.Permissions[0].AccountId
        logging.info("... Authenticated")

    def execute_request(self, api_url, api_request_object=None, method=None):
        """
        perform api request and return result as an instance of ApiObject or list of ApiObjects

        api_url -- absolute or relative api resource url
        api_request_object -- any json serializable object to send to API
        method -- HTTP method of api request. Default: GET if api_request_object is None else POST
        """
        logging.info("Requesting %s", api_url)
        if self._token is None:
            raise ApiException("Access token is not abtained. "
                               "Call authenticate_with_apikey or authenticate_with_contact_credentials first.")

        if not api_url.startswith("http"):
            api_url = self.api_endpoint + api_url

        if method is None:
            if api_request_object is None:
                method = "GET"
            else:
                method = "POST"

        request = urllib.request.Request(api_url, method=method)
        if api_request_object is not None:
            request.data = json.dumps(api_request_object, cls=_ApiObjectEncoder).encode()

        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "application/json")
        request.add_header("Authorization", "Bearer " + self._get_access_token())

        try:
            response = urllib.request.urlopen(request)
            return WaApiClient._parse_response(response)
        except urllib.error.HTTPError as httpErr:
            if httpErr.code == 400:
                raise ApiException(httpErr.read())
            else:
                raise

    def _get_access_token(self):
        expires_at = self._token.retrieved_at + datetime.timedelta(seconds=self._token.expires_in - 100)
        now = datetime.datetime.now()
        if now > expires_at:
            self._refresh_auth_token()
        return self._token.access_token

    def _refresh_auth_token(self):
        logging.info("Refreshing auth token")
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._token.refresh_token
        }
        encoded_data = urllib.parse.urlencode(data).encode()
        request = urllib.request.Request(self.auth_endpoint, encoded_data, method="POST")
        request.add_header("ContentType", "application/x-www-form-urlencoded")
        auth_header = base64.standard_b64encode((self.client_id + ':' + self.client_secret).encode()).decode()
        request.add_header("Authorization", 'Basic ' + auth_header)
        response = urllib.request.urlopen(request)
        self._token = WaApiClient._parse_response(response)
        self._token.retrieved_at = datetime.datetime.now()
        self._accountId = self._token.Permissions[0].AccountId

    def get_events(self):
        events = self.execute_request("/v2/accounts/{}/events".format(self._accountId))
        logging.info("Got %d events", len(events.Events))
        return events.Events

    @staticmethod
    def _parse_response(http_response):
        logging.debug("... parsing response")
        json_data = http_response.read()
        return WaApiClient._parse_data(json.loads(json_data.decode()))

    @staticmethod
    def _parse_data(data):
        if isinstance(data, list):
            result = []
            for item in data:
                result.append(ApiObject(item))
            return result
        elif isinstance(data, dict):
            return ApiObject(data)
        return None

    @staticmethod
    def load_data_from_file(filename):
        logging.info("Loading data from %s",  filename)
        with open(filename, 'rb') as f:
            return pickle.loads(f.read())

    @staticmethod
    def dump_data_to_file(filename, data):
        logging.info("Writing data to %s", filename)
        with open(filename, 'wb') as f:
            p = bytes(pickle.dumps(data))
            f.write(p)


class ApiException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class ApiObject(object):
    """Represent any api call input or output object"""

    def __init__(self, state):
        self.__dict__ = state
        for key, value in vars(self).items():
            if isinstance(value, dict):
                self.__dict__[key] = ApiObject(value)
            elif isinstance(value, list):
                new_list = []
                for list_item in value:
                    if isinstance(list_item, dict):
                        new_list.append(ApiObject(list_item))
                    else:
                        new_list.append(list_item)
                self.__dict__[key] = new_list

    def __str__(self):
        return json.dumps(self.__dict__)

    def __repr__(self):
        return json.dumps(self.__dict__)


class _ApiObjectEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ApiObject):
            return obj.__dict__
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)
