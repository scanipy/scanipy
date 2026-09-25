package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String input040) throws Exception {
        String left040 = "SELECT * FROM orders WHERE id = '";
        String right040 = "'";
        String value040 = _extracted_value(left040, input040, right040);
        Statement st = conn.createStatement();
        st.executeQuery(value040);
    }

    private static String _extracted_value(String left040, String input040, String right040) {
        return left040 + input040 + right040;
    }
}
