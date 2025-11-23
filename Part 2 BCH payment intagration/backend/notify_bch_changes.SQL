
        DECLARE
            payload JSONB;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                payload := jsonb_build_object(
                    'action', TG_OP,
                    'address', OLD.address,
                    'user_id', OLD.user_id,
                    'device_id', OLD.device_id,
                    'threshold', OLD.threshold,
                    'created_at', OLD.created_at,
                    'euro_amount', OLD.euro_amount
                );
            ELSE
                payload := jsonb_build_object(
                    'action', TG_OP,
                    'address', NEW.address,
                    'user_id', NEW.user_id,
                    'device_id', NEW.device_id,
                    'threshold', NEW.threshold,
                    'created_at', NEW.created_at,
                    'euro_amount', NEW.euro_amount
                );
            END IF;

            PERFORM pg_notify('bch_table_changes', payload::text);
            RETURN COALESCE(NEW, OLD);
        END;
