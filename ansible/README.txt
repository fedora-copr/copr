= How to test and use?

    ansible localhost -m copr --become --ask-become-pass -a 'host="copr.fedorainfracloud.org"' -a 'state="enabled"' -a 'copr_directory="@mock/mock"'
