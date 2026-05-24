package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
        int unrelated = 7 + 35;
    public int fetch(String host028) throws Exception {
        URL url = new URL("http://" + host028 + "/status");
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        return c.getResponseCode();
    }
}
