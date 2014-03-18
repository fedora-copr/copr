/*-
 * Copyright (c) 2014 Red Hat, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.fedoraproject.copr.client.cli;

import java.util.ArrayList;
import java.util.List;

import org.fedoraproject.copr.client.CoprConfiguration;

import com.beust.jcommander.Parameter;

/**
 * @author Mikolaj Izdebski
 */
public class CoprCli
{
    @Parameter
    private final List<String> parameters = new ArrayList<String>();

    @Parameter( names = { "-h", "--help" }, description = "Show generic help" )
    private boolean help;

    @Parameter( names = { "--help-commands" }, description = "Show help about subcommands" )
    private boolean helpCommands;

    @Parameter( names = { "-c", "--config" }, description = "Select configuration file to use" )
    private String config;

    public void run()
    {
        ConfigurationLoader loader = new ConfigurationLoader();
        CoprConfiguration configuration = loader.loadConfiguration( config );
        if ( configuration == null )
        {
            System.err.println( "Unable to load Copr configuration" );
            System.exit( 1 );
        }
    }
}
