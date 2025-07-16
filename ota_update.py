
# Pulls files and folders from a GitHub repository

import os
import json
import machine
import time

class OTAUpdate:

    # Repository must be public if no personal auth token is supplied
    user = 'stuffa'
    repository = 'env_sensor'
    branch = 'main'
    token = ''
    _net = None

    # Put the files you don't want deleted or updated
    kept_files = ('/config.json',)


    # Put the files you don't want copied from the repository - if they exist, they are deleted
    # Do not put any "kept_files" in here as they will be deleted
    ignored_files = ('/.gitignore', '/README.md', '/ToDo.txt', '/config_test.json',)


    ### Static URLS ###
    # GitHub uses 'main' instead of master for python repository trees
    git_tree_host = 'https://api.github.com/'
    git_tree_path = f'/repos/{user}/{repository}/git/trees/{branch}?recursive=1'
    git_tree_url  = f'{git_tree_host}{git_tree_path}'

    git_raw_host  = 'https://raw.githubusercontent.com/'
    git_raw_path  = f'/{user}/{repository}/{branch}/'
    git_raw_url   = f'{git_raw_host}{git_raw_path}'

    user_agent = f"'User-Agent': '{user}/{repository}'"


    def __init__(self, net):
        self.net = net


    def get_latest_version(self):
        raw_path = self.git_raw_path + 'version.json'
        headers = { 'User-Agent': f'{self.user}/{self.repository}' } # GitHub Requires user-agent header otherwise 403
        if len(self.token) > 0:
            headers['authorization'] = "bearer %s" % self.token

        r = self.net.get_http(self.git_raw_host, raw_path, headers)
        print(f'http: {r}')
        try:
            ota_latest = json.loads(r)
        except:
            return 0

        return ota_latest['version']


    def update_available(self):
        with open('/version.json', 'rt') as f:
            ota = json.load(f)

        current_version = ota['version']
        next_version = self.get_latest_version()
        return next_version > current_version


    def _pull(self, f_path, raw_url):
        print(f'pulling {f_path} from github')
        try:
            headers = { 'User-Agent': f'{self.user}/{self.repository}' } # GitHub Requires user-agent header otherwise 403
            if len(self.token) > 0:
                headers['authorization'] = "bearer %s" % self.token

            r = self.net.get_http(raw_url, headers=headers)

            with open(f_path, 'w') as new_file:
                new_file.write(r.content.decode('utf-8'))

            os.sync()    
        except:
            print(f'Failed to pull {f_path}')


    def pull_all(self, base_url = git_raw_url):
        git_tree = self._pull_git_tree()
        local_tree = self._build_local_tree()
        local_tree = self._remove_files_from_tree(local_tree, self.kept_files)

        # walk the git tree and make sure we have all the directories
        #  can't be sure that the tree has tree nodes first
        for i in git_tree:
            if i['type'] == 'tree':
                f_path = '/' + i['path']
                try:
                    local_tree = self._remove_file(local_tree, f_path)
                    os.mkdir(f_path)
                except:
                    print(f'failed to create directory {f_path}: dir may already exist')

        # Download each file
        for i in git_tree:
            if i['type'] == 'blob':
                f_path = '/' + i['path']
                if (f_path not in self.kept_files) and (f_path not in self.ignored_files):
                    self._pull(f_path, base_url + i['path'])
                    local_tree = self._remove_file(local_tree, f_path)
     
        # delete the remaining files in the local_tree
        print(local_tree, ' leftover!')
        for i in local_tree:
            os.remove(i)

        os.sync() 
        print('resetting machine in 2 seconds')
        time.sleep(2)
        machine.reset()


    # the local_tree does not contain directories,
    # this means that if we have removed a directory, the files in the directory will be deleted
    # but the empty directory will remain
    def _build_local_tree(self):
        new_tree = []
        os.chdir('/')
        for dir_item in os.listdir():
            self._add_to_tree(new_tree, dir_item)
        return new_tree


    def _add_to_tree(self, tree, dir_item):
        if self._is_directory(dir_item) and len(os.listdir(dir_item)) >= 1:
            os.chdir(dir_item)
            for i in os.listdir():
                self._add_to_tree(tree, i)
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


    def _is_directory(self, file):
        directory = False
        try:
            return os.stat(file)[8] == 0
        except:
            return directory


    def _pull_git_tree(self, tree_url = git_tree_url):
        headers = { 'User-Agent': f'{self.user}/{self.repository}' }   # GitHub Requires user-agent header otherwise 403
        if len(self.token) > 0:
            headers['authorization'] = "bearer %s" % self.token

        r = self.net.get_http(tree_url, headers=headers)
        data = json.loads(r.content.decode('utf-8'))

        if 'tree' not in data:
            print(f'\nBranch "{self.branch}" not found. Set "branch" variable to your branch.\n')
            raise Exception(f'Branch {self.branch} not found.')

        # prune the tree, keep only the data we need    
        git_tree = []
        for i in data['tree']:
            obj = {
                'type': i['type'],
                'path': i['path']
            }
            git_tree.append(obj)

        return git_tree


    def _remove_files_from_tree(self, tree, remove_files):
        new_tree = []
        for i in tree:
            if i not in remove_files:
                new_tree.append(i)
        return new_tree


    def _remove_file(self, tree, file_name):
        new_tree = []
        for name in tree:
            if name != file_name:
                new_tree.append(name)
        return new_tree

# Testing
if __name__ == "__main__":
    from nbiot import NBIoT
    
    nbiot = NBIoT()
    nbiot.enable()
    ota = OTAUpdate(nbiot)
    
    print(f'Latest Version: {ota.get_latest_version()}')
#     print(ota.update_available())
# 
#     git_tree = ota._pull_git_tree()
#     print(git_tree)
# 
#     local_tree = ota._build_local_tree()
#     print(local_tree)
#     local_tree = ota.remove_files_from_tree(local_tree, ota.kept_files)
#     print(local_tree)
#     local_tree = ota.remove_file(local_tree, '/version.json')
#     print(local_tree)
# 
#     pull('/version.json', git_raw_url + 'version.json')
