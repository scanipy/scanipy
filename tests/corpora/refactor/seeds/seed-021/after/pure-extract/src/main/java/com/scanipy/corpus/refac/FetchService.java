package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
    public int fetch(String input020) throws Exception {
        String left020 = "http://";
        String right020 = "/status";
        String value020 = _extracted_value(left020, input020, right020);
        URL url = new URL(value020);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        return connection.getResponseCode();
    }

    private static String _extracted_value(String left020, String input020, String right020) {
        return left020 + input020 + right020;
    }
}
