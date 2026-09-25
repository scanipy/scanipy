package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String input048) throws Exception {
        String left048 = "SELECT * FROM orders WHERE id = '";
        String right048 = "'";
        String[] box = new String[]{input048};
        _mutate(box);
        input048 = box[0];
        String value048 = left048 + input048 + right048;
        Statement st = conn.createStatement();
        st.executeQuery(value048);
    }

    private static void _mutate(String[] box) {
        box[0] = box[0] + "-alias";
    }
}
