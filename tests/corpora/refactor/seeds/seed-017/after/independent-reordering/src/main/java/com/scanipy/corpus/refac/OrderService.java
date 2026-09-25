package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String input016) throws Exception {
        String right016 = "'";
        String left016 = "SELECT * FROM orders WHERE id = '";
        String value016 = left016 + input016 + right016;
        Statement st = conn.createStatement();
        st.executeQuery(value016);
    }
}
