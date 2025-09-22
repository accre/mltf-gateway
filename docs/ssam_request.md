SSAM API endpoints

SSAM provides API endpoints that allow users and programs to communicate with ACCRE slurm. The API documentation can be access from here: https://ssam.accre.vanderbilt.edu/docs
Example 1: Using python to make a slurm request

Please find a python requests example of how a slurm job can be made. Here we will be uploading a small file that will go along with the slurm request. Note: Please note that requests can only allow small attachments along with them. For bigger files, please make sure that it either exists inside the accre or the slurm scripts pull it before they run.

import requests
import json

# slurm directives to request resources
slurm_request = {
    "job_name": "APIJobPython",
    "time": 120, # 120 minutes
    "cpus_per_task": 8, # 8 cores
    "mem": "",
    "tasks_per_node": "",
    "account": "",
    "ntasks": "",
    "nodes": "",
    "nodelist": "",
    "exclude": "",
    "array": "",
    "mail_user": "",
    "mail_type": "",
    "depend": "",
    "constraint": "",
    "partition": "",
    "gres": ""
}

# this is what runs on ACCRE as slurm entrypoint
entry_script =  """
    echo "test"
    stat input/chopper.png
    stat input/file2.png
"""

# Note how we can add multiple files
# https://stackoverflow.com/questions/12385179/how-to-send-a-multipart-form-data-with-requests-in-python
multipart_form_data = [
    ('files', ('chopper.png', open('/path/to/chopper.png', 'rb'))),
    ('files', ('file2.png', open('/path/to/file2.png', 'rb'))),
    # ('files', ('file3.png', open('/path/to/file3.png', 'rb'))),
    ('entry_script', (None, entry_script)),
    ('slurm_request', (None, json.dumps(slurm_request))), # notice the json.dumps
]

token = "<SSAM_Token>"
headers = {"Authorization": f"Bearer {token}"}

response = requests.post('https://ssam.accre.vanderbilt.edu/api/slurm', files=multipart_form_data, headers=headers)
print(response.content)

Response from this request will look like:

{
    "success": true,
    "message": "Slurm job successfully queued for processing",
    "data": {
        "job_uuid": "c7df3567-187f-4e0d-a184-417f51f9c069"}
    }

As one might guess, the responses always have a success and message key in them to make them consistent. In example2, we will see how we can monitor the output and status of the request we just created.
Example 2: Monitoring the job and output

Similar to example1, we will first setup our variables and headers and after that request the /slurm/<uuid> and /slurm/<uuid>/output endpoint to see how our job is doing.

import requests
import json

token = "<SSAM_Token>"
headers = {"Authorization": f"Bearer {token}"}

job_uuid = "JOB_UUID"
url = f'https://ssam.accre.vanderbilt.edu/api/slurm/{job_uuid}'

response = requests.get(url, headers=headers)
print(response.content)

We can see the following output

{
    "success":true,
    "data":{
        "job_uuid":"729a2db7-3401-4b5e-b8fa-7037bc624f7c",
        "job_name":"APIJobPython",
        "user":"accreuser",
        "alternate_user": null,
        "failure_reason":"",
        "job_state":"COMPLETED",
        "created_at":"2024-09-03T16:04:24.948120Z",
        "remote_job_id":"65607858",
        "job_details":{...}
    }
}

Finally, let's look at the output we obtained from our run

job_uuid = "JOB_UUID"
url = f'https://ssam.accre.vanderbilt.edu/api/slurm/{job_uuid}/output'

response = requests.get(url, headers=headers)
print(response.content)

We will see the following output:

{
    "success":true,
    "data":{
        "65607858":"test\\n  File: \'input/chopper.png\'\\n  Size: 0         \\tBlocks: 24         IO Block: 16384  regular empty file\\nDevice: 28h/40d\\tInode: 4152837334  Links: 1\\nAccess: (0644/-rw-r--r--)  Uid: (user_uid/ accreuser)   Gid: (group_gid/   accre)\\nAccess: 2024-09-03 11:06:11.378373000 -0500\\nModify: 2024-09-03 11:04:24.953797000 -0500\\nChange: 2024-09-03 11:06:11.379651440 -0500\\n Birth: -\\n  File: \'input/file2.png\'\\n  Size: 0         \\tBlocks: 24         IO Block: 16384  regular empty file\\nDevice: 28h/40d\\tInode: 1419836716  Links: 1\\nAccess: (0644/-rw-r--r--)  Uid: (user_uid/ accreuser)   Gid: (group_gid/   accre)\\nAccess: 2024-09-03 11:06:11.381457000 -0500\\nModify: 2024-09-03 11:04:24.953797000 -0500\\nChange: 2024-09-03 11:06:11.382651456 -0500\\n Birth: -\\n"
    }
}

When formatted, it looks like:

test
  File: "input/chopper.png"
  Size: 0           Blocks: 24         IO Block: 16384  regular empty file
Device: 28h/40d Inode: 4152837334  Links: 1
Access: (0644/-rw-r--r--)  Uid: (user_uid/ accreuser)   Gid: (group_gid/   accre)
Access: 2024-09-03 11:06:11.378373000 -0500
Modify: 2024-09-03 11:04:24.953797000 -0500
Change: 2024-09-03 11:06:11.379651440 -0500
 Birth: -
  File: "input/file2.png"
  Size: 0           Blocks: 24         IO Block: 16384  regular empty file
Device: 28h/40d Inode: 1419836716  Links: 1
Access: (0644/-rw-r--r--)  Uid: (user_uid/ accreuser)   Gid: (group_gid/   accre)
Access: 2024-09-03 11:06:11.381457000 -0500
Modify: 2024-09-03 11:04:24.953797000 -0500
Change: 2024-09-03 11:06:11.382651456 -0500
 Birth: -
