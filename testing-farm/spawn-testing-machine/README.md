Starting EC2 machine
--------------------

1. setup AWS vars like this (change fields appropriately):

       cat > group_vars/all.yaml <<EOF
       ---
       aws:
         profile: fedora-copr
         # Fedora Cloud 43 -- Paris
         image: ami-055e6291d0779237f
         ssh_key: praiskup
         instance_type: c5a.xlarge
         security_group: CoprSingleHost
         root_volume_size: 60
         infra_subnet: subnet-42f58f2b
       EOF

2. setup AWS credentials/aws config:

       cat ~/.aws/config
       [profile fedora-copr]
       region = us-east-1
       output = table
       $ cast ~/.aws/

       cat ~/.aws/credentials
       [fedora-copr]
       aws_access_key_id=<the-key-id>
       aws_secret_access_key=<the-secret-key>

3. start the machine

       ansible-playbook spawn-test-machine-ec2.yaml

       PLAY [Start new machine] *******************

       TASK [create the testing mock vm in ec2] ***
       changed: [localhost]

       TASK [print ipv4] **************************
       ok: [localhost] => {
           "msg": [
               "Instance ID: i-02f769285490cbb64",
               "Network ID: eni-0298fa7a391ecc42e",
               "Unusable Public IP: 107.20.103.13"
           ]
       }

       PLAY RECAP ********************************
       localhost : ok=2 changed=1 unreachable=0 ...
