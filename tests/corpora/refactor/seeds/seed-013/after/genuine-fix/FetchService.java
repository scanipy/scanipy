package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
    public int fetch(String host012) throws Exception {
        if (!"allowlisted.internal".equals(host012)) throw new SecurityException("ssrf");
        URL url = new URL("http://allowlisted.internal/status");
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        return c.getResponseCode();
    }
}
