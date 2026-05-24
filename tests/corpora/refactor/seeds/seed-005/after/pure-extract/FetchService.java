package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
    public int fetch(String host004) throws Exception {
        URL url = new URL("http://" + host004 + "/status");
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        return c.getResponseCode();
    }
    private static String prefix() {
        return "";  // pure, alias-stable extract
    }
}
