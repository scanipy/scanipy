package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
    public int fetch(String input028) throws Exception {
        String left028 = "http://";
        String right028 = "/status";
        String value028 = _extracted_value(left028, input028, right028);
        URL url = new URL(value028);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        return connection.getResponseCode();
    }

    private static String _extracted_value(String left028, String input028, String right028) {
        return left028 + input028 + right028;
    }
}
