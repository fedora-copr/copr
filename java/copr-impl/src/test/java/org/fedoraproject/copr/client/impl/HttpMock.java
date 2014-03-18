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

import static org.apache.http.HttpStatus.SC_INTERNAL_SERVER_ERROR;
import static org.apache.http.HttpStatus.SC_NOT_FOUND;
import static org.apache.http.HttpStatus.SC_OK;
import static org.apache.http.entity.ContentType.APPLICATION_JSON;
import static org.junit.Assert.fail;

import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;

import org.apache.http.HttpException;
import org.apache.http.HttpRequest;
import org.apache.http.HttpResponse;
import org.apache.http.entity.FileEntity;
import org.apache.http.protocol.HttpContext;
import org.apache.http.protocol.HttpRequestHandler;

/**
 * @author Mikolaj Izdebski
 */
public class HttpMock
    implements HttpRequestHandler
{
    private final RpcTest test;

    public HttpMock( RpcTest test )
    {
        this.test = test;
    }

    @Override
    public void handle( HttpRequest request, HttpResponse response, HttpContext context )
        throws HttpException, IOException
    {
        String uri = request.getRequestLine().getUri();
        String resourceName;

        try
        {
            String method = request.getRequestLine().getMethod();
            if ( method.equals( "GET" ) )
            {
                resourceName = test.getMock().get( uri );
            }
            else if ( method.equals( "POST" ) )
            {
                resourceName = test.getMock().post( uri );
            }
            else
            {
                fail( "Unexpected method: " + method );
                throw new RuntimeException();
            }

            if ( resourceName == null )
            {
                response.setStatusCode( SC_NOT_FOUND );
            }
            else
            {
                Path resourcePath = Paths.get( "src/test/resources" ).resolve( resourceName + ".json" );
                response.setStatusCode( SC_OK );
                response.setEntity( new FileEntity( resourcePath.toFile(), APPLICATION_JSON ) );
            }
        }
        catch ( Exception e )
        {
            response.setStatusCode( SC_INTERNAL_SERVER_ERROR );
        }
    }
}
