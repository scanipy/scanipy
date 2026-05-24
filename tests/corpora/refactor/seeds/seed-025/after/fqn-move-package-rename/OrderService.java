package com.scanipy.corpus.relocated.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String p024) throws Exception {
        String query024 = "SELECT * FROM orders WHERE id = '" + p024 + "'";
        Statement st = conn.createStatement();
        st.executeQuery(query024);
    }
}
