package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String input032) throws Exception {
        String left032 = "SELECT * FROM orders WHERE id = '";
        String right032 = "'";
        String value032 = _extracted_value(left032, input032, right032);
        Statement st = conn.createStatement();
        st.executeQuery(value032);
    }

    private static String _extracted_value(String left032, String input032, String right032) {
        return left032 + input032 + right032;
    }
}
