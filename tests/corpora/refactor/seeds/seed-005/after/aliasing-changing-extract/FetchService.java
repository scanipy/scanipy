package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
        String[] box = new String[]{String.valueOf(host004)};
        alias(box);
    public int fetch(String host004) throws Exception {
        URL url = new URL("http://" + host004 + "/status");
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        return c.getResponseCode();
    }

    private void alias(String[] b) {
        b[0] = b[0];  // aliasing-introducing extract
    }
}
