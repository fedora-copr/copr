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
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import java.util.Iterator;
import java.util.List;

import org.easymock.EasyMockRunner;
import org.fedoraproject.copr.client.CoprException;
import org.fedoraproject.copr.client.ListRequest;
import org.fedoraproject.copr.client.ListResult;
import org.fedoraproject.copr.client.ProjectId;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith( EasyMockRunner.class )
public class ListTest
    extends RpcTest
{
    @Test
    public void testApiFailure()
        throws Exception
    {
        expect( mock.get( "/api/coprs/jdaniels/" ) ).andReturn( "fail" );
        replay( mock );

        ListRequest request = new ListRequest( "jdaniels" );

        try
        {
            session.list( request );
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
        expect( mock.get( "/api/coprs/jdaniels/" ) ).andReturn( null );
        replay( mock );

        ListRequest request = new ListRequest( "jdaniels" );

        try
        {
            session.list( request );
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
        expect( mock.get( "/api/coprs/jdaniels/" ) ).andReturn( "list1" );
        replay( mock );

        ListRequest request = new ListRequest( "jdaniels" );
        ListResult result = session.list( request );

        verify( mock );
        assertEquals( 1, server.getAcceptedConnectionCount() );

        assertNotNull( result );
        List<ProjectId> projects = result.getProjects();

        assertNotNull( projects );
        assertEquals( 1, projects.size() );

        ProjectId project = projects.iterator().next();
        assertEquals( "jdaniels", project.getUserName() );
        assertEquals( "log4j", project.getProjectName() );
    }

    @Test
    public void testMultipleRepos()
        throws Exception
    {
        expect( mock.get( "/api/coprs/johndoe/" ) ).andReturn( "list2" );
        replay( mock );

        ListRequest request = new ListRequest( "johndoe" );
        ListResult result = session.list( request );

        verify( mock );
        assertEquals( 1, server.getAcceptedConnectionCount() );

        assertNotNull( result );
        List<ProjectId> projects = result.getProjects();

        assertNotNull( projects );
        assertEquals( 3, projects.size() );
        Iterator<ProjectId> projectIterator = projects.iterator();

        ProjectId project1 = projectIterator.next();
        assertEquals( "johndoe", project1.getUserName() );
        assertEquals( "log4j", project1.getProjectName() );

        ProjectId project2 = projectIterator.next();
        assertEquals( "johndoe", project2.getUserName() );
        assertEquals( "xyzzy", project2.getProjectName() );

        ProjectId project3 = projectIterator.next();
        assertEquals( "johndoe", project3.getUserName() );
        assertEquals( "my-fancy-repo", project3.getProjectName() );
    }
}
