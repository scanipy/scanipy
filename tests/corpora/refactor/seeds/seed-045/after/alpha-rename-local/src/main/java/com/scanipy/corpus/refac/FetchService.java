package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
    public int fetch(String renamed0) throws Exception {
        String renamed1 = "http://";
        String renamed2 = "/status";
        String renamed3 = renamed1 + renamed0 + renamed2;
        URL url = new URL(renamed3);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        return connection.getResponseCode();
    }
}
