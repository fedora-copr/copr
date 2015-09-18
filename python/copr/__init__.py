from .client import CoprClient

from .client_v2.client import CoprClient as ClientV2

create_client2_from_params = ClientV2.create_from_params
create_client2_from_file_config = ClientV2.create_from_file_config
