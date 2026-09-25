package com.scanipy.corpus.relocated.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String renamed0) throws Exception {
        String renamed1 = "SELECT * FROM orders WHERE id = '";
        String renamed2 = "'";
        String renamed3 = _extracted_value(renamed1, renamed0, renamed2);
        Statement st = conn.createStatement();
        st.executeQuery(renamed3);
    }

    private static String _extracted_value(String renamed1, String renamed0, String renamed2) {
        return renamed1 + renamed0 + renamed2;
    }
}
