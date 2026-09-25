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
        String value040 = "SELECT * FROM orders WHERE id = ?";
        java.sql.PreparedStatement st = conn.prepareStatement(value040);
        st.setString(1, input040);
        st.executeQuery();
    }
}
