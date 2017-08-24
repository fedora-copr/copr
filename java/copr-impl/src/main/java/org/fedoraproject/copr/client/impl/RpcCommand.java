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

import static org.apache.http.entity.ContentType.APPLICATION_JSON;

import java.io.IOException;
import java.io.InputStreamReader;
import java.io.Reader;
import java.net.HttpURLConnection;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Map.Entry;

import javax.xml.bind.DatatypeConverter;

import org.apache.http.HttpResponse;
import org.apache.http.NameValuePair;
import org.apache.http.client.HttpClient;
import org.apache.http.client.entity.UrlEncodedFormEntity;
import org.apache.http.client.methods.HttpGet;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.client.methods.HttpUriRequest;
import org.apache.http.message.BasicNameValuePair;
import org.fedoraproject.copr.client.CoprException;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

/**
 * @author Mikolaj Izdebski
 */
public abstract class RpcCommand<T>
{
    protected abstract String getCommandUrl();

    protected abstract Map<String, String> getExtraArguments();

    protected abstract T parseResponse( JsonObject response );

    protected boolean requiresAuthentication()
    {
        return false;
    }

    public T execute( DefaultCoprSession session )
        throws CoprException
    {
        try
        {
            HttpClient client = session.getClient();

            String baseUrl = session.getConfiguration().getUrl();
            String commandUrl = getCommandUrl();
            String url = baseUrl + commandUrl;

            Map<String, String> extraArgs = getExtraArguments();
            HttpUriRequest request;
            if ( extraArgs == null )
            {
                request = new HttpGet( url );
            }
            else
            {
                HttpPost post = new HttpPost( url );
                request = post;

                List<NameValuePair> nameValuePairs = new ArrayList<NameValuePair>( 2 );
                for ( Entry<String, String> entry : extraArgs.entrySet() )
                {
                    nameValuePairs.add( new BasicNameValuePair( entry.getKey(), entry.getValue() ) );
                }
                post.setEntity( new UrlEncodedFormEntity( nameValuePairs ) );
            }

            if ( requiresAuthentication() )
            {
                String login = session.getConfiguration().getLogin();
                if ( login == null || login.isEmpty() )
                    throw new CoprException( "Authentification is required to perform this command "
                        + "but no login was provided in configuration" );

                String token = session.getConfiguration().getToken();
                if ( token == null || token.isEmpty() )
                    throw new CoprException( "Authentification is required to perform this command "
                        + "but no login was provided in configuration" );

                String auth = login + ":" + token;
                String encodedAuth = DatatypeConverter.printBase64Binary( auth.getBytes( StandardCharsets.UTF_8 ) );
                request.setHeader( "Authorization", "Basic " + encodedAuth );
            }

            request.addHeader( "Accept", APPLICATION_JSON.getMimeType() );

            HttpResponse response = client.execute( request );
            int returnCode = response.getStatusLine().getStatusCode();

            if ( returnCode != HttpURLConnection.HTTP_OK )
            {
                throw new CoprException( "Copr RPC failed: HTTP " + returnCode + " "
                    + response.getStatusLine().getReasonPhrase() );
            }

            Reader responseReader = new InputStreamReader( response.getEntity().getContent() );
            JsonParser parser = new JsonParser();
            JsonObject rpcResponse = parser.parse( responseReader ).getAsJsonObject();

            String rpcStatus = rpcResponse.get( "output" ).getAsString();
            if ( !rpcStatus.equals( "ok" ) )
            {
                throw new CoprException( "Copr RPC returned failure response" );
            }

            return parseResponse( rpcResponse );
        }
        catch ( IOException e )
        {
            throw new CoprException( "Failed to call remote Copr procedure", e );
        }
    }
}
