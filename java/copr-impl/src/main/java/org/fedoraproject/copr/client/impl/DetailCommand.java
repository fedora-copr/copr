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

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Map.Entry;

import org.fedoraproject.copr.client.DetailRequest;
import org.fedoraproject.copr.client.DetailResult;
import org.fedoraproject.copr.client.YumRepository;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

/**
 * @author Mikolaj Izdebski
 */
public class DetailCommand
    extends RpcCommand<DetailResult>
{
    private final DetailRequest request;

    public DetailCommand( DetailRequest request )
    {
        this.request = request;
    }

    @Override
    protected String getCommandUrl()
    {
        return "/api/coprs/" + request.getUserName() + "/" + request.getProjectName() + "/detail/";
    }

    @Override
    protected Map<String, String> getExtraArguments()
    {
        return null;
    }

    @Override
    protected DetailResult parseResponse( JsonObject response )
    {
        JsonObject detail = response.get( "detail" ).getAsJsonObject();

        String additionalRepos = detail.get( "additional_repos" ).getAsString();
        String description = detail.get( "description" ).getAsString();
        String instructions = detail.get( "instructions" ).getAsString();
        long lastModified = detail.get( "last_modified" ).getAsLong();

        JsonObject repos = detail.get( "yum_repos" ).getAsJsonObject();
        List<YumRepository> yumRepos = new ArrayList<>();
        for ( Entry<String, JsonElement> entry : repos.entrySet() )
        {
            String name = entry.getKey();
            String baseUrl = entry.getValue().getAsString();
            YumRepository repo = new YumRepository( name, baseUrl );
            yumRepos.add( repo );
        }

        return new DefaultDetailResult( description, instructions, additionalRepos, yumRepos, lastModified );
    }
}
