package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String p040) throws Exception {
        String query040 = "SELECT * FROM orders WHERE id = '" + p040 + "'";
        Statement st = conn.createStatement();
        st.executeQuery(query040);
    }
}
