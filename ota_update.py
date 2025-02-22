
# Pulls files and folders from open GitHub repository

import os
import urequests
import json
import machine
import time

global internal_tree


# Repository must be public if no personal access token is supplied
user = 'stuffa'
repository = 'env_sensor'
branch = 'main'
token = ''

# Put the files you don't want deleted or updated here use '/filename.ext'
ignore_files = ['/config.json', '/gitignore', '/README.md', '/ToDo.txt']
ignore = ignore_files

# Static URLS
# GitHub uses 'main' instead of master for python repository trees
giturl = 'https://github.com/{user}/{repository}'
call_trees_url = f'https://api.github.com/repos/{user}/{repository}/git/trees/{branch}?recursive=1'
raw = f'https://raw.githubusercontent.com/{user}/{repository}/{branch}/'
user_agent = f"'User-Agent': '{user}/{repository}'"
def update_available():
    with open('/version.json', 'rt') as f:
        ota = json.load(f)
    
    current_version = ota['version']
    next_version = latest_version()
    return next_version > current_version

def latest_version():  
  raw_url = raw + 'version.json'  
  print('raw_url: ' + raw_url)  
  headers = { 'User-Agent': f'{user}/{repository}' } # GitHub Requires user-agent header otherwise 403
  if len(token) > 0:
      headers['authorization'] = "bearer %s" % token 
  r = urequests.get(raw_url, headers=headers)
  try:
    ota_latest = json.loads(r.content.decode('utf-8'))
  except:
    return 0
  return ota_latest['version']


def pull(f_path,raw_url):
  print(f'pulling {f_path} from github')
  #files = os.listdir()
  headers = { 'User-Agent': f'{user}/{repository}' } # GitHub Requires user-agent header otherwise 403
  if len(token) > 0:
      headers['authorization'] = "bearer %s" % token 
  r = urequests.get(raw_url, headers=headers)
  try:
    with open(f_path, 'w') as new_file:
        new_file.write(r.content.decode('utf-8'))
  except:
    print('decode fail try adding non-code files to .gitignore')

def pull_all(raw = raw, ignore = ignore):
  os.chdir('/')
  tree = pull_git_tree()
  internal_tree = build_internal_tree()
  internal_tree = remove_ignore(internal_tree)
  print(' ignore removed ----------------------')
  print(internal_tree)
  log = []
  # download and save all files
  for i in tree['tree']:
    if i['type'] == 'tree':
      try:
        os.mkdir(i['path'])
      except:
        print(f'failed to {i["path"]} dir may already exist')
    elif i['path'] not in ignore:
      try:
        os.remove(i['path'])
        log.append(f'{i["path"]} file removed from int mem')
        internal_tree = remove_item(i['path'],internal_tree)
      except:
        log.append(f'{i["path"]} del failed from int mem')
        print('failed to delete old file')
      try:
        pull(i['path'],raw + i['path'])
        log.append(i['path'] + ' updated')
      except:
        log.append(i['path'] + ' failed to pull')
  # delete files not in Github tree
  if len(internal_tree) > 0:
      print(internal_tree, ' leftover!')
      for i in internal_tree:
          os.remove(i)
          log.append(i + ' removed from int mem')
  logfile = open('ota_log.py','w')
  logfile.write(str(log))
  logfile.close()
  print('resetting machine in 2: machine.reset()')
  time.sleep(2)
  machine.reset()
  #return check instead return with global

  
def build_internal_tree():
  global internal_tree
  internal_tree = []
  os.chdir('/')
  for i in os.listdir():
    add_to_tree(i)
  return internal_tree

def add_to_tree(dir_item):
  global internal_tree
  if is_directory(dir_item) and len(os.listdir(dir_item)) >= 1:
    os.chdir(dir_item)
    for i in os.listdir():
      add_to_tree(i)
    os.chdir('..')
  else:
    print(dir_item)
    if os.getcwd() != '/':
      subfile_path = os.getcwd() + '/' + dir_item
    else:
      subfile_path = os.getcwd() + dir_item
    try:
      print(f'sub_path: {subfile_path}')
      internal_tree.append([subfile_path])
    except OSError: # type: ignore # for removing the type error indicator :)
      print(f'{dir_item} could not be added to tree')

  
def is_directory(file):
  directory = False
  try:
    return os.stat(file)[8] == 0
  except:
    return directory
    
def pull_git_tree(tree_url=call_trees_url):
  headers = { 'User-Agent': f'{user}/{repository}' }   # GitHub Requires user-agent header otherwise 403
  if len(token) > 0:
      headers['authorization'] = "bearer %s" % token 
  r = urequests.get(tree_url,headers=headers)
  data = json.loads(r.content.decode('utf-8'))
  if 'tree' not in data:
      print(f'\nBranch "{branch}" not found. Set "branch" variable to your branch.\n')
      raise Exception(f'Branch {branch} not found.')
  tree = json.loads(r.content.decode('utf-8'))
  return tree
  
def parse_git_tree():
  tree = pull_git_tree()
  dirs = []
  files = []
  for i in tree['tree']:
    if i['type'] == 'tree':
      dirs.append(i['path'])
    if i['type'] == 'blob':
      files.append([i['path'],i['sha'],i['mode']])
  print('dirs:',dirs)
  print('files:',files)
   
   
def check_ignore(ignore = ignore):
  os.chdir('/')
  tree = pull_git_tree()
  # download and save all files
  for i in tree['tree']:
    if i['path'] not in ignore:
        print(i['path'] + ' not in ignore')
    if i['path'] in ignore:
        print(i['path']+ ' is in ignore')
        
def remove_ignore(internal_tree, ignore = ignore):
    clean_tree = []
    int_tree = []
    for i in internal_tree:
        int_tree.append(i[0])
    for i in int_tree:
        if i not in ignore:
            clean_tree.append(i)
    return clean_tree
        
def remove_item(item,tree):
    culled = []
    for i in tree:
        if item not in i:
            culled.append(i)
    return culled
