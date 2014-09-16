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
import static org.junit.Assert.fail;

import java.util.Iterator;
import java.util.List;

import org.easymock.EasyMockRunner;
import org.fedoraproject.copr.client.CoprException;
import org.fedoraproject.copr.client.PlaygroundListRequest;
import org.fedoraproject.copr.client.PlaygroundListResult;
import org.fedoraproject.copr.client.ProjectId;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith( EasyMockRunner.class )
public class PlaygroundListTest
    extends RpcTest
{
    @Test
    public void testApiFailure()
        throws Exception
    {
        expect( mock.get( "/api/playground/list/" ) ).andReturn( "fail" );
        replay( mock );

        PlaygroundListRequest request = new PlaygroundListRequest();

        try
        {
            session.playgroundList( request );
            fail();
        }
        catch ( CoprException e )
        {
            verify( mock );
            assertEquals( 1, server.getAcceptedConnectionCount() );
        }
    }

    @Test
    public void testPlaygroundList()
        throws Exception
    {
        expect( mock.get( "/api/playground/list/" ) ).andReturn( "playground" );
        replay( mock );

        PlaygroundListRequest request = new PlaygroundListRequest();
        PlaygroundListResult result = session.playgroundList( request );

        verify( mock );
        assertEquals( 1, server.getAcceptedConnectionCount() );

        assertNotNull( result );
        List<ProjectId> projects = result.getProjects();

        assertNotNull( projects );
        assertEquals( 3, projects.size() );
        Iterator<ProjectId> projectIterator = projects.iterator();

        ProjectId project1 = projectIterator.next();
        assertEquals( "sochotni", project1.getUserName() );
        assertEquals( "fedwatch", project1.getProjectName() );

        ProjectId project2 = projectIterator.next();
        assertEquals( "bkabrda", project2.getUserName() );
        assertEquals( "python-3.4", project2.getProjectName() );

        ProjectId project3 = projectIterator.next();
        assertEquals( "james", project3.getUserName() );
        assertEquals( "yum-rawhide", project3.getProjectName() );
    }
}
