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

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import org.fedoraproject.copr.client.CoprConfiguration;
import org.ini4j.Wini;

/**
 * @author Mikolaj Izdebski
 */
public class ConfigurationLoader
{
    private String getEvnDefault( String key, Object defaultValue )
    {
        String value = System.getenv( key );
        if ( value == null || value.isEmpty() )
            return defaultValue.toString();

        return value;
    }

    private void addXdgBasePath( List<Path> configPaths, String location )
    {
        Path base = Paths.get( location );
        if ( !base.isAbsolute() )
            return;

        Path path = base.resolve( "copr" );
        if ( Files.isRegularFile( path ) )
            configPaths.add( path );
    }

    public CoprConfiguration loadConfiguration( String customPath )
    {
        List<Path> configPaths = new ArrayList<>();

        if ( customPath != null )
        {
            configPaths.add( Paths.get( customPath ) );
        }
        else
        {
            Path xdgHome = Paths.get( getEvnDefault( "HOME", System.getProperty( "user.home" ) ) );
            addXdgBasePath( configPaths, getEvnDefault( "XDG_CONFIG_HOME", xdgHome.resolve( ".config" ) ) );

            for ( String part : getEvnDefault( "XDG_CONFIG_DIRS", "/etc/xdg" ).split( ":" ) )
                addXdgBasePath( configPaths, part );

            Collections.reverse( configPaths );
        }

        CoprConfiguration configuration = new CoprConfiguration();

        for ( Path path : configPaths )
        {
            try
            {
                Wini wini = new Wini( path.toFile() );

                String url = wini.get( "copr-cli", "copr_url" );
                if ( url != null )
                    configuration.setUrl( url );

                String login = wini.get( "copr-cli", "login" );
                if ( login != null )
                    configuration.setLogin( login );

                String token = wini.get( "copr-cli", "token" );
                if ( token != null )
                    configuration.setToken( token );
            }
            catch ( IOException e )
            {
                return null;
            }
        }

        return configuration;
    }
}
