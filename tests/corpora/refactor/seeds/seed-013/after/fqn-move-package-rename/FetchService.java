package com.scanipy.corpus.relocated.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
    public int fetch(String host012) throws Exception {
        URL url = new URL("http://" + host012 + "/status");
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        return c.getResponseCode();
    }
}
