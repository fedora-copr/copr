.. _beaker_tests:

Beaker tests
============

Start the following three jobs in Beaker::

    <job retention_tag="scratch">
        <whiteboard>
            Test Copr (F25)
        </whiteboard>

        <recipeSet priority="Normal">
            <recipe kernel_options="" kernel_options_post="" ks_meta="method=nfs" role="None" whiteboard="">
                <autopick random="false"/>
                <watchdog panic="None"/>
                <packages/>
                <ks_appends/>
                <repos/>
                <distroRequires>
                    <and>
                        <distro_name op="=" value="Fedora-25"/>
                        <distro_arch op="=" value="x86_64"/>
                    </and>
                    <distro_virt op="=" value=""/>
                </distroRequires>

                <hostRequires>
                    <and>
                        <key_value key="MEMORY" op="&gt;" value="1"/>
                        <key_value key="DISK" op="&gt;" value="1"/>
                    </and>
                    <system_type value="Machine"/>
                </hostRequires>

                <partitions/>

                <task name="/distribution/install" role="None"/>
                <task name="/CoreOS/Spacewalk/Installer/Workaround/disable-beaker-repo" role="None"/>
                <task name="/tools/tests/Install/Config-copr-cli" role="None"/>
                <task name="/tools/test.copr/Regression/Copr-cli" role="None"/>
                <task name="/tools/copr/Sanity/copr-cli-basic-operations" role="None"/>
            </recipe>
        </recipeSet>
    </job>

::

    <job>
        <whiteboard>
            copr-dist-git test
        </whiteboard>

        <recipeSet>
            <recipe>
                <distroRequires>
                    <and>
                        <distro_family op="=" value="Fedora25"/>
                        <distro_arch op="=" value="x86_64"/>
                    </and>
                </distroRequires>

                <hostRequires>
                    <system_type value="Machine"/>
                </hostRequires>

                <task name="/distribution/install" role="STANDALONE"/>
                <task name="/tools/copr/Regression/dist-git" role="STANDALONE">
                    <params>
                        <param name="RELEASETEST" value="true"/> <!-- to use released versions of COPR packages in the test -->
                    </params>
                </task>
            </recipe>
        </recipeSet>
    </job>

::

    <job>
        <whiteboard>
            copr-backend test
        </whiteboard>

        <recipeSet>
            <recipe>
                <distroRequires>
                    <and>
                        <distro_family op="=" value="Fedora25"/>
                        <distro_arch op="=" value="x86_64"/>
                    </and>
                </distroRequires>

                <hostRequires>
                    <system_type value="Machine"/>
                    <key_value key="HVM" op="=" value="1"/>
                </hostRequires>

                <task name="/distribution/install" role="STANDALONE"/>
                <task name="/tools/copr/Regression/backend" role="STANDALONE">
                    <params>
                        <param name="RELEASETEST" value="true"/> <!-- to use released versions of COPR packages in the test -->
                    </params>
                </task> 
            </recipe>
        </recipeSet>
    </job>


You can also run the tests locally.

You can do so in a docker environment that is ready to use for running the tests in isolation from your host::

	$ cd DockerTestEnv
	$ make && make run        # this takes a while
	$ make sh
	# cd ./Regression/dist-git
	# ./runtest.sh

There are some options for runtest.sh that can help you with debugging (especially running just a subset 
of tests with '-r' might be useful) and you can read README file (in the same dir) for their usage. Note
that these options are not (yet) present for tests in 'Sanity' subdirectory, only for ones in 'Regression'
subdir.

At the end whole test-suite should pass.
