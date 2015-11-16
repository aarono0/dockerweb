#!/usr/bin/python
# -*- coding:UTF-8 -*-

import docker, os, time
from flask import Flask, request, url_for, g, session, render_template, redirect

# Init Flask 
app = Flask(__name__)

# Connect the docker daemon
def connect_docker():
    return docker.Client(base_url='unix://var/run/docker.sock', timeout = 300)

@app.before_request
def before_request():
    g.connect = connect_docker()

# The CPU/MEM util format
def mem_format(mem):
    if mem >= 1024**3:
        mem = str(mem / (1024**3))+'G'
    elif mem >= 1024**2:
        mem = str(mem / (1024**2))+'M'
    elif mem >= 1024:
        mem = str(mem / 1024)+'K'
    else:
        mem = str(mem)+'B'
    return mem
    
# Date and time format
def datetime_format(asctime):
    return time.strftime("%Y/%m/%d %H:%M ", time.localtime(asctime))

# Get the system info    
def get_info():
    host_info = {}
    docker_info = {}
    storage_usage = {}
    infos = g.connect.info()
    for k, v in infos.items():
        if k in ['Name', 'KernelVersion', 'OperatingSystem', 'MemTotal', 'NCPU']:
            host_info[k] = v
        elif k in ['Containers', 'Images', 'Driver', 'OomKillDisable', 'IPv4Forwarding', 'BridgeNfIptables', 'DockerRootDir', ]:
            docker_info[k] = v
        elif k == 'DriverStatus':
            for i in v:
                if 'Data Space' in i[0]:
                    storage_usage[i[0]] = i[1]
    return (host_info, docker_info, storage_usage)

# Get the images info
def get_images():
    imgs = g.connect.images()
    image_list = []
    for i in imgs:
        for t in i['RepoTags']:
            print t
            repotag = "".join(t)
            data = repotag.split(':')
            data.append(i['Id'][:12])
            data.append(datetime_format(i['Created']))
            data.append(mem_format(i['VirtualSize']))
            image_list.append(data)
    return image_list

# Remove image
def delete_image(id):
    g.connect.remove_image(id)

# Save_image, next version support
def save_image(id, path):
    image = g.connect.get_image(id)
    image_tar = open(path, 'w')
    image_tar.write(image.data)
    image_tar.close()

# Get the containers info
def get_containers():
    containers = g.connect.containers(all=True)
    container_list = []
    for i in containers:
        data = []
        ports = []
        data.append("".join(i['Names'])[1::])
        data.append(i['Image'])
        data.append(i['Id'][:12])
        data.append(datetime_format(i['Created']))
        data.append(i['Status'])
        '''
        for p in i['Ports']:
            if 'IP' in p.keys():
                ports.append(p['IP']+":"+str(p['PublicPort'])+"->"+str(p['PrivatePort'])+'/'+p['Type'])
        ports = " ".join(ports)
        data.append(ports)
        '''
        container_list.append(data)
    return container_list

# Stop container    
def stop_container(id):
    g.connect.stop(id)

# Restart container    
def reboot_container(id):
    g.connect.restart(id)

# Pasue container
def pause_container(id):
    g.connect.pause(id)

# Unpuse container    
def recover_container(id):
    g.connect.unpause(id)


# Kill container    
def kill_container(id):
    g.connect.kill(id)

# Delete container    
def delete_container(id):
    g.connect.remove_container(id, force = True)

# Get the container detail infomation
def get_container_detail(id):
    detail = []
    mappports = []
    mounts = []
    details = g.connect.inspect_container(id)
    ports = details['NetworkSettings'].get('Ports', None)
    if ports is not None:
        for i in ports:
            if ports[i] is not None:
                mappports.append(ports[i][0]['HostIp']+':'+ports[i][0]['HostPort']+'->'+i)
            
    else:
        mappports = "None"
    if details.get('Mounts', None) is not None:
        for i in details['Mounts']:
            mounts.append(i['Source']+':'+i['Destination'])
    else:
        mounts = "None"

    if details['Config'].get('Hostname', None) is not None:
        detail.append(details['Config']['Hostname'])
    if details['NetworkSettings'].get('IPAddress', None) is not None:
        detail.append(details['NetworkSettings']['IPAddress'])
    if details['NetworkSettings'].get('MacAddress', None) is not None:
        detail.append(details['NetworkSettings']['MacAddress'])
    if details['NetworkSettings'].get('Gateway', None):
        detail.append(details['NetworkSettings']['Gateway'])
    
    detail.append(mappports)
    detail.append(mounts)
    
    if details['Config'].get('Cmd', None) is not None:
        cmd = " ".join(details['Config']['Cmd'])
        detail.append(cmd)
    else:
        detail.append("None")
    
    if details['Config'].get('Entrypoint', None) is not None:
        entrypoint = " ".join(details['Config']['Entrypoint'])
        detail.append(entrypoint)
    else:
        detail.append("None")
    return detail
    
# Container Action Option
action = {'STOP' : stop_container, 'REBOOT' : reboot_container,
'PAUSE' : pause_container, 'RECOVER' : recover_container,
'KILL' : kill_container, 'DELETE' : delete_container
}

# Index Page View
@app.route('/index')
def index():
    return render_template('index.html', host_info = get_info()[0], docker_info = get_info()[1], storage_usage = get_info()[2])

# Images Manage Page View    
@app.route('/images', methods = ['GET', 'POST'])
def images():
    if request.method == 'POST':
        #return render_template('page.html',data = request.form)
        if request.form.get('action', None) == 'delete':
            g.connect.remove_image(request.form['repotag'])
            return redirect('/images')
        elif request.form.get('boot', None) == 'commit':
            new_container = g.connect.create_container(image=request.form['repotag'], name=request.form['name'], command=request.form['command'])
            g.connect.start(new_container)
            return redirect('/containers')
    return render_template('images.html', images_list = get_images())

# Containers Manage Page View
@app.route('/containers', methods = ['GET', 'POST'])
def containers():
    if request.method == 'POST':
        option = request.form['action']
        id = request.form['id']
        if option in action.keys():
            action[option](id)
        return redirect('/containers')
    return render_template('containers.html', containers_list = get_containers(), actionlist = action.keys(), inspect = get_container_detail)

# Run Server	
if __name__ == '__main__':
    app.run(host = '0.0.0.0',port = 8080)
