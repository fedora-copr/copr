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

import java.net.InetSocketAddress;

import org.apache.http.localserver.LocalTestServer;
import org.easymock.Mock;
import org.easymock.MockType;
import org.fedoraproject.copr.client.CoprConfiguration;
import org.fedoraproject.copr.client.CoprService;
import org.fedoraproject.copr.client.CoprSession;
import org.junit.After;
import org.junit.Before;

/**
 * @author Mikolaj Izdebski
 */
public abstract class RpcTest
{
    protected LocalTestServer server;

    protected String url;

    protected CoprSession session;

    @Mock( type = MockType.STRICT )
    protected RpcMock mock;

    public RpcMock getMock()
    {
        return mock;
    }

    protected CoprConfiguration getConfiguration()
    {
        return new CoprConfiguration();
    }

    @Before
    public void setUp()
        throws Exception
    {
        server = new LocalTestServer( null, null );
        server.register( "/api/*", new HttpMock( this ) );
        server.start();

        InetSocketAddress address = server.getServiceAddress();
        url = "http://" + address.getHostName() + ":" + address.getPort();

        CoprConfiguration configuration = getConfiguration();
        configuration.setUrl( url );

        CoprService copr = new DefaultCoprService();

        session = copr.newSession( configuration );
    }

    @After
    public void tearDown()
        throws Exception
    {
        server.stop();
    }
}
