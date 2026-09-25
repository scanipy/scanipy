package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
    public int fetch(String input044) throws Exception {
        String left044 = "http://";
        String right044 = "/status";
        String value044 = _extracted_value(left044, input044, right044);
        URL url = new URL(value044);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        return connection.getResponseCode();
    }

    private static String _extracted_value(String left044, String input044, String right044) {
        return left044 + input044 + right044;
    }
}
