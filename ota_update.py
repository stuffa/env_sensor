
# Pulls files and folders from open GitHub repository

import os
import urequests
import json
import machine
import time

# Repository must be public if no personal auth token is supplied
user = 'stuffa'
repository = 'env_sensor'
branch = 'main'
token = ''

# Put the files you don't want deleted or updated
kept_files = ('/config.json',)


# Put the files you don't want copied from the repository - if they exist they are deleted
ignored_files = ('/.gitignore', '/README.md', '/ToDo.txt',)


### Static URLS ###
# GitHub uses 'main' instead of master for python repository trees
git_tree_url = f'https://api.github.com/repos/{user}/{repository}/git/trees/{branch}?recursive=1'
git_raw_url  = f'https://raw.githubusercontent.com/{user}/{repository}/{branch}/'
user_agent = f"'User-Agent': '{user}/{repository}'"


def update_available():
    with open('/version.json', 'rt') as f:
        ota = json.load(f)

    current_version = ota['version']
    next_version = get_latest_version()
    return next_version > current_version


def get_latest_version():
    raw_url = git_raw_url + 'version.json'
    headers = { 'User-Agent': f'{user}/{repository}' } # GitHub Requires user-agent header otherwise 403
    if len(token) > 0:
        headers['authorization'] = "bearer %s" % token

    r = urequests.get(raw_url, headers=headers)
    try:
        ota_latest = json.loads(r.content.decode('utf-8'))
    except:
        return 0

    return ota_latest['version']


def pull(f_path, raw_url):
    print(f'pulling {f_path} from github')
    try:
        headers = { 'User-Agent': f'{user}/{repository}' } # GitHub Requires user-agent header otherwise 403
        if len(token) > 0:
            headers['authorization'] = "bearer %s" % token

        r = urequests.get(raw_url, headers=headers)
    
        with open(f_path, 'w') as new_file:
            new_file.write(r.content.decode('utf-8'))
        
        os.sync()    
    except:
        print(f'Failed to pull {f_path}')


def pull_all(base_url = git_raw_url):
    git_tree = pull_git_tree()
    local_tree = build_local_tree()
    local_tree = remove_files_from_tree(local_tree, kept_files)

    # walk the git tree and make sure we have all the directories
    # cant be sure that the tree has tree nodes first
    for i in git_tree:
        if i['type'] == 'tree':
            f_path = '/' + i['path']
            try:
                local_tree = remove_file(local_tree, f_path)
                os.mkdir(f_path)
            except:
                print(f'failed to create directory {f_path}: dir may already exist')

    # Now dowload each file
    for i in git_tree:
        if i['type'] == 'blob':
            f_path = '/' + i['path']
            if (f_path not in kept_files) and (f_path not in ignored_files):
                pull(f_path, base_url + i['path'])
                local_tree = remove_file(local_tree, f_path)
 
    # delete the remaining files in the local_tree
    print(local_tree, ' leftover!')
    for i in local_tree:
        os.remove(i)

    os.sync() 
    print('resetting machine in 2 seconds')
    time.sleep(2)
    machine.reset()


# the local_tree does not contain directries
# thsi means that if we have removed a directory the files in the directory will be deleted
# but the empty directry wil remain
def build_local_tree():
    new_tree = []
    os.chdir('/')
    for dir_item in os.listdir():
        add_to_tree(new_tree, dir_item)
    return new_tree


def add_to_tree(tree, dir_item):
    if is_directory(dir_item) and len(os.listdir(dir_item)) >= 1:
        os.chdir(dir_item)
        for i in os.listdir():
            add_to_tree(tree, i)
        os.chdir('..')
    else:
        if os.getcwd() != '/':
            subfile_path = os.getcwd() + '/' + dir_item
        else:
            subfile_path = os.getcwd() + dir_item
        try:
            tree.append(subfile_path)
        except OSError: # type: ignore # for removing the type error indicator :)
            print(f'{dir_item} could not be added to tree')

  
def is_directory(file):
    directory = False
    try:
        return os.stat(file)[8] == 0
    except:
        return directory


def pull_git_tree(tree_url = git_tree_url):
    headers = { 'User-Agent': f'{user}/{repository}' }   # GitHub Requires user-agent header otherwise 403
    if len(token) > 0:
        headers['authorization'] = "bearer %s" % token

    r = urequests.get(tree_url,headers=headers)
    data = json.loads(r.content.decode('utf-8'))

    if 'tree' not in data:
        print(f'\nBranch "{branch}" not found. Set "branch" variable to your branch.\n')
        raise Exception(f'Branch {branch} not found.')

    # prune the tree, keep only the data we need    
    git_tree = []
    for i in data['tree']:
        obj = {
            'type': i['type'],
            'path': i['path']
        }
        git_tree.append(obj)
        
    return git_tree


def remove_files_from_tree(tree, remove_files):
    new_tree = []
    for i in tree:
        if i not in remove_files:
            new_tree.append(i)
    return new_tree


def remove_file(tree, file_name):
    new_tree = []
    for name in tree:
        if name != file_name:
            new_tree.append(name)
    return new_tree

# Testing
# if __name__ == "__main__":
#     print(pull_git_tree())
#     local_tree = build_local_tree()
#     print(local_tree)
#     local_tree = remove_files_from_tree(local_tree, kept_files)
#     print(local_tree)
#     local_tree = remove_file(local_tree, '/version.json')
#     print(local_tree)
#     pull('/version.json', git_raw_url + 'version.json')
#     