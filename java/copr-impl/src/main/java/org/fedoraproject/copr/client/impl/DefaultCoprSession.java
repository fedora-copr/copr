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
package org.fedoraproject.copr.client.impl;

import org.apache.http.client.HttpClient;
import org.apache.http.impl.client.HttpClients;
import org.fedoraproject.copr.client.BuildRequest;
import org.fedoraproject.copr.client.BuildResult;
import org.fedoraproject.copr.client.CoprConfiguration;
import org.fedoraproject.copr.client.CoprException;
import org.fedoraproject.copr.client.CoprSession;
import org.fedoraproject.copr.client.DetailRequest;
import org.fedoraproject.copr.client.DetailResult;
import org.fedoraproject.copr.client.ListRequest;
import org.fedoraproject.copr.client.ListResult;
import org.fedoraproject.copr.client.PlaygroundListRequest;
import org.fedoraproject.copr.client.PlaygroundListResult;

/**
 * @author Mikolaj Izdebski
 */
public class DefaultCoprSession
    implements CoprSession
{
    private final CoprConfiguration configuration;

    private final HttpClient client;

    public DefaultCoprSession( CoprConfiguration configuration )
    {
        this.configuration = configuration;
        client = HttpClients.createDefault();
    }

    public HttpClient getClient()
    {
        return client;
    }

    public CoprConfiguration getConfiguration()
    {
        return configuration;
    }

    @Override
    public void close()
        throws CoprException
    {
    }

    @Override
    public ListResult list( ListRequest request )
        throws CoprException
    {
        ListCommand command = new ListCommand( request );
        return command.execute( this );
    }

    @Override
    public PlaygroundListResult playgroundList( PlaygroundListRequest request )
        throws CoprException
    {
        PlaygroundListCommand command = new PlaygroundListCommand( request );
        return command.execute( this );
    }

    @Override
    public DetailResult detail( DetailRequest request )
        throws CoprException
    {
        DetailCommand command = new DetailCommand( request );
        return command.execute( this );
    }

    @Override
    public BuildResult build( BuildRequest request )
        throws CoprException
    {
        BuildCommand command = new BuildCommand( request );
        return command.execute( this );
    }
}
