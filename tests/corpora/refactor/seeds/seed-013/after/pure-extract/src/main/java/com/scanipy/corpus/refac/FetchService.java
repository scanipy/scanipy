package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
    public int fetch(String input012) throws Exception {
        String left012 = "http://";
        String right012 = "/status";
        String value012 = _extracted_value(left012, input012, right012);
        URL url = new URL(value012);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        return connection.getResponseCode();
    }

    private static String _extracted_value(String left012, String input012, String right012) {
        return left012 + input012 + right012;
    }
}
