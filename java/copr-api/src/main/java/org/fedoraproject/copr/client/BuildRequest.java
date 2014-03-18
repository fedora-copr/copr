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
package org.fedoraproject.copr.client;

import java.util.Collection;
import java.util.LinkedHashSet;
import java.util.Set;

/**
 * @author Mikolaj Izdebski
 */
public class BuildRequest
{
    private String userName;

    private String projectName;

    private final Set<String> srpms = new LinkedHashSet<>();

    private String memory;

    private String timeout;

    public BuildRequest()
    {
    }

    public BuildRequest( String userName, String projectName )
    {
        this.userName = userName;
        this.projectName = projectName;
    }

    public String getUserName()
    {
        return userName;
    }

    public void setUserName( String userName )
    {
        this.userName = userName;
    }

    public String getProjectName()
    {
        return projectName;
    }

    public void setProjectName( String projectName )
    {
        this.projectName = projectName;
    }

    public Collection<String> getSourceRpmList()
    {
        return srpms;
    }

    public void addSourceRpm( String url )
    {
        srpms.add( url );
    }

    public void removeSourceRpm( String url )
    {
        srpms.remove( url );
    }

    public String getMemory()
    {
        return memory;
    }

    public void setMemory( String memory )
    {
        this.memory = memory;
    }

    public String getTimeout()
    {
        return timeout;
    }

    public void setTimeout( String timeout )
    {
        this.timeout = timeout;
    }
}
