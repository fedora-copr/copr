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

import java.util.Collections;
import java.util.Date;
import java.util.List;

import org.fedoraproject.copr.client.DetailResult;
import org.fedoraproject.copr.client.YumRepository;

/**
 * @author Mikolaj Izdebski
 */
public class DefaultDetailResult
    implements DetailResult
{
    private final String description;

    private final String instructions;

    private final String additionalRepos;

    private final List<YumRepository> yumRepositories;

    private final Date lastModified;

    public DefaultDetailResult( String description, String instructions, String additionalRepos,
                                List<YumRepository> yumRepositories, long lastModified )
    {
        this.description = description;
        this.instructions = instructions;
        this.additionalRepos = additionalRepos;
        this.yumRepositories = Collections.unmodifiableList( yumRepositories );
        this.lastModified = new Date( lastModified );
    }

    @Override
    public String getDescription()
    {
        return description;
    }

    @Override
    public String getInstructions()
    {
        return instructions;
    }

    @Override
    public String getAdditionalRepos()
    {
        return additionalRepos;
    }

    @Override
    public List<YumRepository> getYumRepositories()
    {
        return yumRepositories;
    }

    @Override
    public Date getLastModified()
    {
        return lastModified;
    }
}
