package org.fedoraproject.copr.client;

public class YumRepository
{
    private String name;

    private String baseUrl;

    public YumRepository()
    {
    }

    public YumRepository( String name, String baseUrl )
    {
        this.name = name;
        this.baseUrl = baseUrl;
    }

    public String getName()
    {
        return name;
    }

    public void setName( String name )
    {
        this.name = name;
    }

    public String getBaseUrl()
    {
        return baseUrl;
    }

    public void setBaseUrl( String baseUrl )
    {
        this.baseUrl = baseUrl;
    }
}
