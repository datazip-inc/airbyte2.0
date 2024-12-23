#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Mapping, Union

import requests
from requests import HTTPError

from airbyte_cdk.sources.declarative.auth.declarative_authenticator import NoAuth
from airbyte_cdk.sources.declarative.interpolation import InterpolatedString
from airbyte_cdk.sources.declarative.types import Config


# https://developers.zoom.us/docs/internal-apps/s2s-oauth/#successful-response
# The Bearer token generated by server-to-server token will expire in one hour


@dataclass
class CustomYouniumAuthenticator(NoAuth):
    config: Config

    username: Union[InterpolatedString, str]
    password: Union[InterpolatedString, str]
    legal_entity: Union[InterpolatedString, str]
    grant_type: Union[InterpolatedString, str]
    client_id: Union[InterpolatedString, str]
    scope: Union[InterpolatedString, str]

    _access_token = None
    _token_type = None

    def __post_init__(self, parameters: Mapping[str, Any]):
        self._username = InterpolatedString.create(self.username, parameters=parameters).eval(self.config)
        self._password = InterpolatedString.create(self.password, parameters=parameters).eval(self.config)
        self._legal_entity = InterpolatedString.create(self.legal_entity, parameters=parameters).eval(self.config)
        self._grant_type = InterpolatedString.create(self.grant_type, parameters=parameters).eval(self.config)
        self._client_id = InterpolatedString.create(self.client_id, parameters=parameters).eval(self.config)
        self._scope = InterpolatedString.create(self.scope, parameters=parameters).eval(self.config)

    def __call__(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        """Attach the page access token to params to authenticate on the HTTP request"""
        if self._access_token is None or self._token_type is None:
            self._access_token, self._token_type = self.generate_access_token()

        headers = {self.auth_header: f"{self._token_type} {self._access_token}", "Content-type": "application/json"}

        request.headers.update(headers)

        return request

    @property
    def auth_header(self) -> str:
        return "Authorization"

    @property
    def token(self) -> str:
        return self._access_token

    def generate_access_token(self) -> (str, str):
        # return (str("token123"), str("Bearer"))
        try:
            headers = {"Content-Type": "application/x-www-form-urlencoded"}

            data = {
                "username": self._username,
                "password": self._password,
                "legal_entity": self._legal_entity,
                "grant_type": self._grant_type,
                "client_id": self._client_id,
                "scope": self._scope,
            }

            if self.config.get("playground"):
                url = "https://younium-identity-server-sandbox.azurewebsites.net/connect/token"
                # url = "http://localhost:3000/playground/auth/token"
            else:
                url = "https://younium-identity-server.azurewebsites.net/connect/token"
                # url = "http://localhost:3000/auth/token"

            rest = requests.post(url, headers=headers, data=data)
            if rest.status_code != HTTPStatus.OK:
                raise HTTPError(rest.text)
            return (rest.json().get("access_token"), rest.json().get("token_type"))
        except Exception as e:
            raise Exception(f"Error while generating access token: {e}") from e
