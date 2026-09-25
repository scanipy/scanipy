package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
    public int fetch(String input044) throws Exception {
        String left044 = "http://";
        String right044 = "/status";
        String value044 = left044 + input044 + right044;
        URL url = new URL(value044);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        return connection.getResponseCode();
    }
}
