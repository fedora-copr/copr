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
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import java.util.Date;
import java.util.Iterator;

import org.easymock.EasyMockRunner;
import org.fedoraproject.copr.client.CoprException;
import org.fedoraproject.copr.client.DetailRequest;
import org.fedoraproject.copr.client.DetailResult;
import org.fedoraproject.copr.client.YumRepository;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith( EasyMockRunner.class )
public class DetailTest
    extends RpcTest
{
    @Test
    public void testApiFailure()
        throws Exception
    {
        expect( mock.get( "/api/coprs/mizdebsk/override/detail/" ) ).andReturn( "fail" );
        replay( mock );

        DetailRequest request = new DetailRequest( "mizdebsk", "override" );

        try
        {
            session.detail( request );
            fail();
        }
        catch ( CoprException e )
        {
            verify( mock );
            assertEquals( 1, server.getAcceptedConnectionCount() );
        }
    }

    @Test
    public void test404()
        throws Exception
    {
        expect( mock.get( "/api/coprs/mizdebsk/override/detail/" ) ).andReturn( null );
        replay( mock );

        DetailRequest request = new DetailRequest( "mizdebsk", "override" );

        try
        {
            session.detail( request );
            fail();
        }
        catch ( CoprException e )
        {
            verify( mock );
            assertEquals( 1, server.getAcceptedConnectionCount() );

            assertTrue( e.getMessage().contains( "404 Not Found" ) );
        }
    }

    @Test
    public void testSingleRepo()
        throws Exception
    {
        expect( mock.get( "/api/coprs/mizdebsk/override/detail/" ) ).andReturn( "detail1" );
        replay( mock );

        DetailRequest request = new DetailRequest( "mizdebsk", "override" );
        DetailResult result = session.detail( request );

        verify( mock );
        assertEquals( 1, server.getAcceptedConnectionCount() );

        assertNotNull( result );
        assertEquals( "Fixed or tweaked versions of some Fedora packages, for personal use.", result.getDescription() );
        assertEquals( "Nothing complicated, really...", result.getInstructions() );
        assertEquals( "", result.getAdditionalRepos() );
        assertEquals( new Date( 1407916203 ), result.getLastModified() );

        Iterator<YumRepository> it = result.getYumRepositories().iterator();
        assertTrue( it.hasNext() );
        YumRepository repo1 = it.next();
        assertEquals( "fedora-20-x86_64", repo1.getName() );
        assertEquals( "http://copr-be.cloud.fedoraproject.org/results/mizdebsk/override/fedora-20-x86_64/",
                      repo1.getBaseUrl() );
        YumRepository repo2 = it.next();
        assertEquals( "fedora-21-x86_64", repo2.getName() );
        assertEquals( "http://copr-be.cloud.fedoraproject.org/results/mizdebsk/override/fedora-21-x86_64/",
                      repo2.getBaseUrl() );
        YumRepository repo3 = it.next();
        assertEquals( "fedora-rawhide-x86_64", repo3.getName() );
        assertEquals( "http://copr-be.cloud.fedoraproject.org/results/mizdebsk/override/fedora-rawhide-x86_64/",
                      repo3.getBaseUrl() );
        assertFalse( it.hasNext() );
    }
}
