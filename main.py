import yaml
from os import listdir
from os.path import isfile, join

import settings
log = settings.log
from auth_utils import *


#-----client info-----
def handle_validate_client(auth, client_name):
    """
    Checks if the given the client_name value from the config.yaml file matches the name of an existing
    Client in Plextrac. If the client exists in platform, returns the client_id. Otherwise displays a list
    of clients for the user to pick and returns the selected client_id.
    """
    response = request_list_clients(auth.base_url, auth.get_auth_headers())
    if type(response) != list:
        log.critical(f'Could not retrieve clients from instance. Exiting...')
        exit()
    if len(response) < 1:
        input = prompt_user_options(f'There are no clients in the instance. Would you like to create a new client?', "Invalid option", ["y", "n"])
        if input == "y":
            return handle_create_new_client(auth)

    if client_name == "":
        input = prompt_user_options("client_name was not added to config. Do you want to pick an existing or create a new client", "Invalid option", ["pick", "create"])
        if input == "pick":
            return pick_client(auth, response)
        elif input == "create":
            return handle_create_new_client(auth)
    
    clients = list(filter(lambda x: client_name in x['data'], response))

    if len(clients) > 1:
        log.warning(f'client_name value \'{client_name}\' from config matches {len(clients)} Clients in platform. Will need to select one manually...')
        return pick_client(auth, response)

    if len(clients) < 1:
        log.warning(f'Could not find client named \'{client_name}\' in platform. Will need to select one manually...')
        return pick_client(auth, response)

    if len(clients) == 1:
        # example request_list_clients response
        # [
        #   {
        #     "id": "client_1912",
        #     "doc_id": [
        #       1912
        #     ],
        #     "data": [
        #       1912,
        #       "test client",
        client_id = clients[0].get('data')[0]
        log.debug(f'found 1 client with matching name in config with client_id {client_id}')
        log.success(f'Found {client_name} client in your PT instance')
        return client_id, client_name

def pick_client(auth, clients):
    """
    Display the list of clients in the instance to the user and prompts them to picka client.
    Returns the clinet_id of the selected client.
    """
    log.info(f'List of Report Templates in tenant {auth.tenant_id}:')
    for index, client in enumerate(clients):
        log.info(f'Index: {index+1}   Name: {client.get("data")[1]}')

    client_index = prompt_user_list("Please enter a client index from the list above.", "Index out of range.", len(clients))
    client = clients[client_index]
    client_id = client.get('data')[0]
    client_name = client.get("data")[1]
    log.debug(f'returning picked client with client_id {client_id}')
    log.info(f'Selected Client: {client_index+1} - {client_name}')

    return client_id, client_name

def handle_create_new_client(auth):
    """
    Creates a new client and returns the new client_id.
    """
    client_name = prompt_user("Enter the name of a new Client to be created.")
    client_data = {
        'name': client_name
    }
    log.info(f'Creating new client with name \'{client_name}\'')

    response = request_create_client(auth.base_url, auth.get_auth_headers(), client_data)
    if response.get('client_id') == None:
        if not prompt_retry("Could not create client."):
            exit()
        return handle_create_new_client(auth)

    log.success(f'Created new client \'{client_name}\'')
    log.debug(f'created client \'{client_name}\' with client_id {response.get("client_id")}')
    return response.get('client_id'), client_name

#-----end client info-----


#-----ptrac info-----
def handle_load_ptracs(folder_path):
    """
    Takes a relative path to a folder and returns a list[str] of joined file path and file name for all ptracs in the folder.
    If a folder_path was not set in hte config, the user will be prompted.
    """
    if folder_path == "":
        folder_path = prompt_user(f'Enter the relative path to the directory containing the ptracs you want to import')

    files = [f for f in listdir(folder_path) if isfile(join(folder_path, f))] # list of all files
    ptracs = [f for f in files if f.split(".")[-1] == "ptrac"] # list of all ptracs determined by file extension
    if len(ptracs) < 1:
        if prompt_user_options(f'Could not find any PTRAC files in specified directory. Pick another directory?', "Invalid option", ["y", "n"]) == "y":
            return handle_load_ptracs("")
        exit()

    log.success(f'Found {len(ptracs)} PTRAC file(s) in {folder_path}')
    return folder_path, ptracs

def verify_ptrac(ptrac_str_data):
    """
    Take a string, verifies the string is a valid JSON and has the required keys to be a PTRAC.
    Returns a dict object of the PTRAC
    """
    valid = True
    data = {}

    # is the file a JSON
    try:
        data = json.loads(ptrac_str_data)
    except Exception as e:
        log.error("Malformed file cannot be read as a JSON")
        valid = False

    # report_info
    if data.get('report_info') == None:
        log.warning("Invalid PTRAC does not contain the key report_info")
        valid = False
    # flaws_array
    if data.get('flaws_array') == None:
        log.warning("Invalid PTRAC does not contain the key flaws_array")
        valid = False
    # summary
    if data.get('summary') == None:
        log.warning("Invalid PTRAC does not contain the key summary")
        valid = False
    # evidence
    if data.get('evidence') == None:
        log.warning("Invalid PTRAC does not contain the key evidence")
        valid = False
    # client_info
    if data.get('client_info') == None:
        log.warning("Invalid PTRAC does not contain the key client_info")
        valid = False

    return valid, data

#-----end ptrac info-----


if __name__ == '__main__':
    settings.print_script_info()

    with open("config.yaml", 'r') as f:
        args = yaml.safe_load(f)

    auth = Auth(args)
    auth.handle_authentication()

    # get client to import to
    client_name = ""
    if args.get('client_name') != None and args.get('client_name') != "":
        client_name = args.get('client_name')
        log.info(f'Validating client \'{client_name}\' from config...')
    client_id, client_name = handle_validate_client(auth, client_name)

    # get files to import
    folder_path = ""
    if args.get('folder_path') != None and args.get('folder_path') != "":
        folder_path = args.get('folder_path')
        log.info(f'Using folder path \'{folder_path}\' from config...')
    folder_path, ptracs = handle_load_ptracs(folder_path)

    # 'FolderName' and 'FolderName/' will both find the correct directory
    # path needs to be known moving forward
    if folder_path[-1] == "/":
        folder_path = folder_path[:-1]

    # import files
    if prompt_user_options(f'Import {len(ptracs)} PTRAC file(s) to client {client_name}', "Invalid option", ["y", "n"]) == "y":
        successful_imports = 0
        for index, ptrac in enumerate(ptracs):
            log.info(f'({index+1}/{len(ptracs)}): Loading {ptrac}')
            # open as text to verify ptrac
            with open(f'{folder_path}/{ptrac}', 'r', encoding='utf-8') as f:
                valid, data = verify_ptrac(f.read())
                if not valid:
                    log.warning(f'Invalid PTRAC. Skipping...')
                    continue
            # open as file to send in request
            log.info("Verified file. Importing PTRAC...")
            with open(f'{folder_path}/{ptrac}', 'rb') as f:
                response = request_import_report_from_ptrac(auth.base_url, auth.get_auth_headers(), client_id, f)
                if response.get('status') == "success":
                    log.success(f'Successfully imported {ptrac} to {client_name}')
                    successful_imports += 1
        
        log.success(f'Successfully imported {successful_imports}/{len(ptracs)} files')
