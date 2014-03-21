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

import static org.easymock.EasyMock.expect;
import static org.easymock.EasyMock.replay;
import static org.easymock.EasyMock.verify;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.fail;

import org.easymock.EasyMockRunner;
import org.fedoraproject.copr.client.BuildRequest;
import org.fedoraproject.copr.client.BuildResult;
import org.fedoraproject.copr.client.CoprConfiguration;
import org.fedoraproject.copr.client.CoprException;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith( EasyMockRunner.class )
public class BuildTest
    extends RpcTest
{
    @Override
    protected CoprConfiguration getConfiguration()
    {
        CoprConfiguration config = super.getConfiguration();

        config.setLogin( "test-login" );
        config.setToken( "p4s5w0rd" );

        return config;
    }

    @Test
    public void testBuild()
        throws Exception
    {
        expect( mock.post( "/api/coprs/john/toy/new_build/" ) ).andReturn( "build1" );
        replay( mock );

        BuildRequest request = new BuildRequest( "john", "toy" );

        BuildResult result = session.build( request );

        verify( mock );
        assertEquals( 1, server.getAcceptedConnectionCount() );

        assertEquals( "Build was added to log4j.", result.getMessage() );
        assertEquals( 5, result.getBuildId() );
    }

    @Test
    public void testBuildFail()
        throws Exception
    {
        expect( mock.post( "/api/coprs/john/toy/new_build/" ) ).andReturn( "fail" );
        replay( mock );

        BuildRequest request = new BuildRequest( "john", "toy" );

        try
        {
            session.build( request );
            fail();
        }
        catch ( CoprException e )
        {
            verify( mock );
            assertEquals( 1, server.getAcceptedConnectionCount() );
        }
    }
}
