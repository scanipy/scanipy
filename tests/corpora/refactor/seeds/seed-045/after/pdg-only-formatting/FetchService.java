// reformatted (no semantic change)

package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {

    public int fetch(String host044) throws Exception {

        URL url = new URL("http://" + host044 + "/status");
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        return c.getResponseCode();
    }
}
