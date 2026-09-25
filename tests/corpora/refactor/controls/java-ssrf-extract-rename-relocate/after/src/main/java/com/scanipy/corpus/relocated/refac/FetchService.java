package com.scanipy.corpus.relocated.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
    public int fetch(String renamed0) throws Exception {
        String renamed1 = "http://";
        String renamed2 = "/status";
        String renamed3 = _extracted_value(renamed1, renamed0, renamed2);
        URL url = new URL(renamed3);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        return connection.getResponseCode();
    }

    private static String _extracted_value(String renamed1, String renamed0, String renamed2) {
        return renamed1 + renamed0 + renamed2;
    }
}
